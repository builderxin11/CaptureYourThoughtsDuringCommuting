"""
Lambda A: Upload Handler
- Receives multipart/form-data audio from iOS Shortcut via API Gateway
- Saves audio to S3 under pending/<uuid>.<ext>
- Returns 202 Accepted immediately so iPhone gets quick feedback
"""

import base64
import cgi
import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
BUCKET = os.environ["AUDIO_BUCKET"]

# Supported audio MIME types → file extensions
MIME_TO_EXT = {
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/aac": "aac",
    "application/octet-stream": "m4a",  # iOS sometimes sends this
}


def handler(event, context):
    try:
        audio_bytes, ext, original_filename = extract_audio(event)
    except ValueError as e:
        return response(400, {"error": str(e)})

    memo_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    s3_key = f"pending/{timestamp}_{memo_id}.{ext}"

    # Store metadata alongside the audio so the processor has context
    metadata = {
        "memo_id": memo_id,
        "original_filename": (original_filename or f"recording.{ext}").encode("ascii", "ignore").decode("ascii"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=audio_bytes,
        ContentType=f"audio/{ext}",
        Metadata={k: str(v) for k, v in metadata.items()},
    )

    logger.info("Saved audio to s3://%s/%s (%d bytes)", BUCKET, s3_key, len(audio_bytes))

    return response(
        202,
        {
            "message": "Got it, processing your thought now.",
            "memo_id": memo_id,
            "s3_key": s3_key,
        },
    )


def extract_audio(event: dict) -> Tuple[bytes, str, Optional[str]]:
    """
    Supports two upload styles from iOS Shortcuts:
      1. multipart/form-data  (field name: "audio")
      2. Raw binary body with Content-Type: audio/*
    """
    content_type = (event.get("headers") or {}).get(
        "content-type", event.get("headers", {}).get("Content-Type", "")
    )
    body_b64 = event.get("isBase64Encoded", False)
    raw_body = event.get("body", "")

    body_bytes: bytes = (
        base64.b64decode(raw_body) if body_b64 else raw_body.encode("latin-1")
    )

    # ── Multipart ──────────────────────────────────────────────────────────────
    if "multipart/form-data" in content_type:
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body_bytes)),
        }
        form = cgi.FieldStorage(
            fp=io.BytesIO(body_bytes),
            environ=environ,
            keep_blank_values=True,
        )
        if "audio" not in form:
            raise ValueError("Multipart body must contain an 'audio' field")

        field = form["audio"]
        audio_bytes = field.file.read()
        original_filename = field.filename
        mime = field.type or "audio/m4a"
        ext = MIME_TO_EXT.get(mime, "m4a")
        return audio_bytes, ext, original_filename

    # ── Raw binary ─────────────────────────────────────────────────────────────
    for mime, ext in MIME_TO_EXT.items():
        if mime in content_type:
            return body_bytes, ext, None

    raise ValueError(
        f"Unsupported Content-Type: {content_type}. "
        "Send multipart/form-data with field 'audio', or raw audio/m4a binary."
    )


def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
