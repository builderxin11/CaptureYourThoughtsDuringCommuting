# Notion Database Setup

## Required Database Properties

Create a new Notion database (full-page) with these exact property names and types:

| Property Name | Type | Notes |
|---------------|------|-------|
| `Title` | Title | Default — already exists |
| `Date` | Date | Recording date |
| `Transcript` | Text | First 2000 chars (full text is in page body) |
| `Original Audio Link` | URL | Pre-signed S3 link (7-day expiry) |

## Get Your Database ID

1. Open your Notion database in a browser
2. The URL looks like: `https://www.notion.so/yourworkspace/abc123def456...?v=...`
3. The database ID is the 32-character string before the `?v=` — e.g., `abc123def456ghi789jkl012mno34567`
4. Add hyphens if your integration needs UUID format: `abc123de-f456-ghi7-89jk-l012mno34567`

## Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click **New integration**
3. Name it `VoiceToNotion`, select your workspace
4. Copy the **Internal Integration Token** (starts with `secret_`)
5. In your database page → click **...** menu → **Add connections** → select `VoiceToNotion`

## Verify
After deploying, run a test upload and check:
- Page appears in the database
- Title is auto-generated from transcript
- Date is today
- Transcript field has content
- Audio Link opens a downloadable file
