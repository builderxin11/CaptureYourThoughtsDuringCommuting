"""
Lambda B: Processor
- Triggered by S3 ObjectCreated event on pending/ prefix
- Downloads audio, sends to Gemini for transcription
- Parses structured output, creates a Notion database page
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import boto3
import google.generativeai as genai

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
NOTION_VERSION = "2022-06-28"

# Use Flash model — fast and cheap for audio transcription
GEMINI_MODEL = "gemini-3-flash-preview"

TRANSCRIPTION_PROMPT = """
You are a personal assistant transcribing a voice memo recorded while commuting.

Transcribe the audio accurately and completely. Then provide a short title (max 8 words)
that captures the main idea. Return your response as valid JSON with this exact schema:

{
  "title": "<concise title>",
  "transcript": "<full verbatim transcript>"
}

If the audio is unclear or empty, use:
{
  "title": "Unclear Recording",
  "transcript": "[Audio was unclear or contained no speech]"
}
"""


def handler(event, context):
    for record in event.get("Records", []):
        # SQS wraps the S3 notification as a JSON string in the message body
        if "body" in record:
            import json as _json
            s3_event = _json.loads(record["body"])
            s3_records = s3_event.get("Records", [])
        else:
            s3_records = [record]

        for s3_record in s3_records:
            bucket = s3_record["s3"]["bucket"]["name"]
            key = s3_record["s3"]["object"]["key"]

            logger.info("Processing s3://%s/%s", bucket, key)

            try:
                process_audio(bucket, key)
            except Exception as exc:
                logger.exception("Failed to process %s: %s", key, exc)
                failed_key = key.replace("pending/", "failed/", 1)
                s3.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": key},
                    Key=failed_key,
                )
                s3.delete_object(Bucket=bucket, Key=key)
                raise


def process_audio(bucket: str, key: str):
    # ── Download audio from S3 ─────────────────────────────────────────────────
    obj = s3.get_object(Bucket=bucket, Key=key)
    audio_bytes = obj["Body"].read()
    metadata = obj.get("Metadata", {})
    uploaded_at = metadata.get("uploaded_at", datetime.now(timezone.utc).isoformat())
    original_filename = metadata.get("original_filename", "recording.m4a")

    ext = key.rsplit(".", 1)[-1].lower()
    mime_map = {"m4a": "audio/mp4", "mp3": "audio/mpeg", "wav": "audio/wav", "aac": "audio/aac"}
    mime_type = mime_map.get(ext, "audio/mp4")

    # Build the S3 URL for the Notion page (pre-signed, 7-day expiry)
    audio_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=604800,  # 7 days
    )

    # ── Transcribe with Gemini ─────────────────────────────────────────────────
    title, transcript = transcribe_with_gemini(audio_bytes, mime_type)
    logger.info("Transcription complete. Title: %s", title)

    # ── Create Notion page ─────────────────────────────────────────────────────
    notion_url = create_notion_page(
        title=title,
        transcript=transcript,
        recorded_at=uploaded_at,
        audio_url=audio_url,
        original_filename=original_filename,
    )
    logger.info("Notion page created: %s", notion_url)

    # Move audio to processed/ prefix
    processed_key = key.replace("pending/", "processed/", 1)
    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": key},
        Key=processed_key,
    )
    s3.delete_object(Bucket=bucket, Key=key)


def transcribe_with_gemini(audio_bytes: bytes, mime_type: str) -> tuple[str, str]:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Upload audio inline (Gemini supports up to ~20MB inline)
    audio_part = {"mime_type": mime_type, "data": audio_bytes}

    response = model.generate_content(
        [TRANSCRIPTION_PROMPT, audio_part],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw = response.text.strip()

    # Strip markdown code fences if model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
        title = parsed.get("title", "Voice Memo").strip() or "Voice Memo"
        transcript = parsed.get("transcript", "").strip()
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON, using raw text as transcript")
        title = "Voice Memo"
        transcript = raw

    return title, transcript


def create_notion_page(
    title: str,
    transcript: str,
    recorded_at: str,
    audio_url: str,
    original_filename: str,
) -> str:
    """Creates a page in the Notion database and returns its URL."""

    # Parse ISO date for Notion date property
    try:
        dt = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        date_str = dt.date().isoformat()
    except ValueError:
        date_str = datetime.now(timezone.utc).date().isoformat()

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {
                "title": [{"text": {"content": title}}]
            },
            "Date": {
                "date": {"start": date_str}
            },
            "Original Audio Link": {
                "url": audio_url
            },
            "Transcript": {
                "rich_text": [{"text": {"content": transcript[:2000]}}]
            },
        },
        # Full transcript as page body (handles >2000 char limit on property)
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Full Transcript"}}]
                },
            },
            *_transcript_to_blocks(transcript),
            {
                "object": "block",
                "type": "divider",
                "divider": {},
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": f"Original file: {original_filename}"},
                        }
                    ]
                },
            },
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        "https://api.notion.com/v1/pages",
        data=data,
        headers={
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
        method="POST",
    )

    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode()
        logger.error("Notion API error %s: %s", e.code, body)
        raise RuntimeError(f"Notion API returned {e.code}: {body}") from e

    return result.get("url", "")


def _transcript_to_blocks(transcript: str) -> list[dict]:
    """Split long transcript into 2000-char Notion paragraph blocks."""
    blocks = []
    chunk_size = 2000
    for i in range(0, max(len(transcript), 1), chunk_size):
        chunk = transcript[i : i + chunk_size]
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            }
        )
    return blocks
