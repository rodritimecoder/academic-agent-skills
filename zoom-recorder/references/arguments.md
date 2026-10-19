# CLI Arguments

| Argument | Description | Default |
|---|---|---|
| `--url <url>` | Zoom cloud recording URL (`/rec/play` or `/rec/share`) | Required |
| `--passcode, -p <pwd>` | Recording passcode (if protected) | `""` |
| `--out-dir, -o <dir>` | Destination folder for saved files | `.` |
| `--format` | Output format: `md` (Markdown), `vtt` (raw WebVTT), `txt` (plain text), `all` | `md` |
| `--keyframes` | Stream video with ffmpeg to extract slide changes | Disabled |
| `--scene-threshold` | Sensitivity for slide change scene detection (`0.0` - `1.0`) | `0.35` |
| `--table, -t` | Render output as high-density Markdown pipe tables | Disabled |
| `--outline, --agenda` | Extract high-density chronological agenda/outline table (~200 tokens) | Disabled |
| `--info-only, --info` | Retrieve recording metadata only without downloading files | Disabled |
| `--project <fields>` | Comma-separated fields to project in output (e.g. `topic,duration`) | Disabled |
| `--limit, -n <N>` | Cap the number of outline rows returned | `0` (unlimited) |
| `--json` | Print extracted recording metadata or outline to stdout as JSON | Disabled |

## Local OCR models

`--ocr-model` selects a local GGUF vision model, and `all` benchmarks every
one of them on the same extracted slides.

| Model | Strength |
|---|---|
| `lighton` | LightOnOCR-3-1B — blazing fast (<1s), clean Markdown layout, accurate LaTeX equations |
| `xiaomi` | Xiaomi-OCR-0 — reasoning OCR, LaTeX formulas, clean formatting |
| `deskforge` | DeskForge-Qwen3.5-4B — document and Markdown hierarchy preservation, units formatted (`\mu\text{F}`) |
| `ovis` | OvisOCR2-5B — high-detail UI and on-screen text extraction |
