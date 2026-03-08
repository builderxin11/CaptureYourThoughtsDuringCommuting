# iOS Shortcut Setup — Voice to Notion

## What It Does
"Hey Siri, capture thought" → records audio → POSTs to your API → iPhone says "Got it, processing."

---

## Step-by-Step: Build the Shortcut

### 1. Create a new Shortcut
Open **Shortcuts** app → tap **+** → rename it **"Capture Thought"**

### 2. Add: Record Audio
- Search action: **Record Audio**
- Set **Recording Starts**: Immediately
- Set **Recording Stops**: On Tap (or use a fixed duration like 60s for hands-free)

> **Hands-free tip**: Set "Stop Recording" = After 60 seconds, or use "When I Stop Speaking" (Transcribe My Voice action can detect silence).

### 3. Add: Get Contents of URL
This is the HTTP request action.

| Field | Value |
|-------|-------|
| URL | `https://<your-api-id>.execute-api.us-east-1.amazonaws.com/prod/upload` |
| Method | `POST` |
| Headers | `x-api-key` → `<your-api-key>` |
| Request Body | **Form** |
| Form field name | `audio` |
| Form field value | `Recorded Audio` (the variable from step 2) |
| File name | `recording.m4a` |

> iOS Shortcuts sends audio as `audio/x-m4a` in multipart/form-data. The Lambda handles this automatically.

### 4. Add: Speak Text
- Add action: **Speak Text**
- Text: `Got it, processing your thought.`

Or use **Show Notification** for silent operation.

### 5. Add Siri Phrase
- Tap the Shortcut name → **Add to Siri**
- Record: **"Capture thought"**

---

## Hands-Free / Driving Mode Tips

- Enable **Driving Focus** and allow this Shortcut in Focus settings
- Set the shortcut to auto-start: use **Personal Automation** → When CarPlay Connects → run a "background ready" variant
- For completely hands-free recording: use **"Ask Each Time"** duration or **Auto Stop on Silence** (requires iOS 17+)

---

## Testing
1. Open Shortcuts app → tap "Capture Thought" manually
2. Check your Notion database — a new page should appear within ~15–30 seconds
3. Check CloudWatch Logs (`/aws/lambda/voice-to-notion-processor`) if nothing appears

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 403 Forbidden | Wrong or missing `x-api-key` | Check API key in Shortcut headers |
| 202 but no Notion page | Processor Lambda failed | Check CloudWatch logs |
| "Unclear Recording" in Notion | Audio was too short or silent | Speak louder, check mic permissions |
| Notion page has no title | Database properties mismatch | Ensure your DB has: Title, Date, Transcript, Original Audio Link |
