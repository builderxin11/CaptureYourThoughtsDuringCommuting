# Capture Your Thoughts During Commuting

A fire-and-forget voice memo pipeline that turns speech recorded on your iPhone into structured Notion pages — automatically, while you drive.

**Say "Hey Siri, capture thought" → speak → done.** The transcript appears in Notion within ~15–30 seconds.

---

## How It Works

```
iPhone (iOS Shortcut)
  └─► POST /upload (API Gateway + Lambda)
        └─► S3 (pending/)
              └─► SQS trigger → Lambda Processor
                    ├─► Google Gemini (transcription + title)
                    └─► Notion API (creates database page)
```

1. **iOS Shortcut** records audio and POSTs it to the API endpoint
2. **Upload Lambda** saves the audio to S3 and immediately returns `202 Accepted` so your phone gets instant feedback
3. **S3 → SQS** event triggers the Processor Lambda
4. **Processor Lambda** sends the audio to Gemini Flash for transcription, then creates a Notion page with the title, transcript, date, and a link to the original audio
5. Audio files auto-delete from S3 after 7 days

---

## Architecture

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| API endpoint | API Gateway (REST) | Receives audio from iOS, API key auth |
| Upload handler | Lambda (`voice-to-notion-upload`) | Parses multipart or raw audio, writes to S3 |
| Message queue | SQS + DLQ | Decouples upload from processing, retries up to 3× |
| Audio storage | S3 | Temporary audio store with 7-day lifecycle |
| Processor | Lambda (`voice-to-notion-processor`) | Transcribes via Gemini, writes to Notion |
| IaC | AWS SAM | One-command deploy |

---

## Prerequisites

- AWS CLI configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed
- Google Gemini API key (get one at [aistudio.google.com](https://aistudio.google.com))
- Notion integration token and database (see [Notion Setup](docs/notion-setup.md))
- iPhone with the iOS Shortcut configured (see [iOS Shortcut Setup](docs/ios-shortcut-setup.md))

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/builderxin11/CaptureYourThoughtsDuringCommuting.git
cd CaptureYourThoughtsDuringCommuting
```

### 2. Configure secrets

Copy the example and fill in your values:

```bash
cp .env.example samconfig.toml
```

Edit `samconfig.toml` with your real keys:

| Key | Where to get it |
|-----|----------------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) |
| `NOTION_API_KEY` | [Notion integrations page](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | From your Notion database URL |
| `API_KEY` | Any random string — used by the iOS Shortcut to authenticate |

> See [docs/notion-setup.md](docs/notion-setup.md) for step-by-step Notion instructions.

### 3. Deploy

```bash
./deploy.sh
```

This runs `sam build` and `sam deploy`. After a successful deploy, the output will show your **Upload Endpoint URL** — copy it for the next step.

### 4. Set up the iOS Shortcut

Follow [docs/ios-shortcut-setup.md](docs/ios-shortcut-setup.md) to configure the "Capture Thought" shortcut and add it to Siri.

---

## Notion Page Structure

Each voice memo creates a Notion page with:

| Property | Content |
|----------|---------|
| **Title** | Auto-generated summary (≤8 words) from Gemini |
| **Date** | Recording date |
| **Transcript** | First 2000 characters |
| **Original Audio Link** | Pre-signed S3 URL (valid 7 days) |
| **Page body** | Full transcript (no length limit) |

---

## Supported Audio Formats

The upload Lambda accepts:

- `audio/m4a` / `audio/x-m4a` (default from iOS)
- `audio/mp4`
- `audio/mpeg` (MP3)
- `audio/wav`
- `audio/aac`
- `application/octet-stream` (iOS fallback)

Sent as `multipart/form-data` (field name: `audio`) or raw binary body.

---

## Error Handling

- If the Processor Lambda fails, the audio is moved to `s3://…/failed/` and the SQS message is retried up to 3 times before landing in the Dead Letter Queue
- Check CloudWatch Logs at `/aws/lambda/voice-to-notion-processor` for details
- Common issues are covered in the [iOS Shortcut troubleshooting guide](docs/ios-shortcut-setup.md#troubleshooting)

---

## Docs

- [iOS Shortcut Setup](docs/ios-shortcut-setup.md) — build the Shortcut, add Siri phrase, driving mode tips, troubleshooting
- [Notion Database Setup](docs/notion-setup.md) — required properties, get your database ID, create the integration

---

## Cost

All components run within AWS free tier limits for personal use:
- Lambda: 1M free requests/month
- SQS: 1M free requests/month
- S3: negligible for small audio files with 7-day auto-delete
- API Gateway: 1M free calls/month (first 12 months)
- Gemini Flash: very low cost for audio transcription

---

## License

MIT
