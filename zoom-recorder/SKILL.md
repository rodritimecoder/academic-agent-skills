---
name: zoom-recorder
description: >
  Download transcripts, slide keyframes, and metadata from Zoom cloud
  recordings without API admin credentials. Handles passcode-protected
  links, unwraps Mimecast and SafeLinks wrappers, and OCRs the slides with
  local vision models.
---

# Zoom Recorder (`zoom-recorder`)

Downloads Zoom cloud recordings (`/rec/play/…` and `/rec/share/…`) focused
on **transcripts and presentation keyframes**, never the hour-long video
file. Transcripts come back as Markdown with timestamps and speaker tags;
slides come back as OCR'd images, benchmarked across four local models.

---

## 🏛️ What It Does

| Capability | How it works | Example question |
| :--- | :--- | :--- |
| **Passcode support** | Institutional recordings (`utsmeet.zoom.us`, `*.zoom.us`) are authenticated through Zoom's own web playback validation — no admin API credentials | *"Download a recording my university protected with a passcode"* |
| **Transcript first** | Native `.vtt` captions and speaker transcripts in milliseconds, formatted to Markdown with timestamps and speaker tags | *"Get the transcript of this lecture"* |
| **URL unwrapping** | Unrolls Mimecast and Microsoft SafeLinks protection wrappers automatically | *"This link is a Mimecast redirect"* |
| **Selective keyframes** | Streams the video into ffmpeg with scene-change detection (`select='gt(scene,0.35)'`), then OCRs the slides locally | *"Pull the slides out of this recording"* |
| **Canvas integration** | Scans course modules and pages with `canvas-cli`, extracts the Zoom URL and passcode, and writes transcripts into the course notes directory | *"Get the transcript for this week's tutorial"* |

---

## 🛠️ CLI Quickstart

```bash
ZR="/run/media/rodri/AI/skills/zoom-recorder/scripts"

# 1. Download a Markdown transcript
python3 $ZR/zoom_download.py --url "<recording-url>" --passcode "<pwd>" --out-dir ./transcripts --format md

# 2. Extract slide keyframes and OCR them with a local model
python3 $ZR/zoom_download.py --url "<recording-url>" --passcode "<pwd>" --ocr --ocr-model lighton --out-dir ./slides

# 3. Benchmark every local OCR model against the same slides
python3 $ZR/zoom_download.py --url "<recording-url>" --passcode "<pwd>" --ocr --ocr-model all --out-dir ./benchmark

# 4. Inspect recording metadata without downloading anything
python3 $ZR/zoom_download.py --url "<recording-url>" --passcode "<pwd>" --info-only --table

# 5. Extract a 20-line lecture outline (~200 tokens, not a 50k-token transcript)
python3 $ZR/zoom_download.py --url "<recording-url>" --passcode "<pwd>" --outline --table --limit 15

# 6. Pull every recording out of a Canvas course, with passcodes
python3 /run/media/rodri/AI/skills/zoom-recorder/examples/canvas_zoom_pipeline.py --course-id <id> --out-dir <dir> --format md
```

---

## Reference

- `references/arguments.md` — every flag, its meaning, and its default
- `references/canvas-pipeline.md` — how the Canvas scan works, and the downstream `cornell-notes` step
