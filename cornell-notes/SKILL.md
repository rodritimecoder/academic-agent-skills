---
name: cornell-notes
description: Convert existing Markdown (.md) notes into clean, print-ready Cornell Notes HTML with active-recall cue–note pairs, interactive self-quiz mode, and section summaries. Use whenever asked to convert notes, format into Cornell notes, make Cornell notes, create revision notes, export to Anki, or prepare print-ready study notes from a markdown document.
---

# Cornell Notes Formatting Skill

This skill transforms existing Markdown (`.md`) study/lecture/technical notes into clean, print-ready Cornell Notes HTML documents optimized for active recall, on-screen self-quizzing, and A4 printing.

The source notes already exist. The LLM understands the source structure, synthesizes content into paired cues, notes, and summaries, and saves an intermediate JSON file. A local Python script then deterministically formats and renders standalone HTML with embedded CSS.

**Never overwrite the original Markdown file.**

---

## Workflow

1. **Read Source Markdown**:
   - Read the user's target Markdown file using filesystem/read tools.
   - Retain all core concepts, definitions, formulas, code snippets, tables, callouts, and external links.

2. **Transform into Cornell Notes Schema**:
   - Reorganize content into logical sections.
   - For each section, formulate **active-recall cue–note pairs**:
     - **Cues (left column, ~32% width)**: Active questions ("What is...?", "Why does... happen?", "Compare..."), keywords, or prompts.
     - **Notes (right column, ~68% width)**: Concise yet complete explanations, bullet points, code blocks, tables, or callouts directly answering the cue.
   - Formulate a **section summary**: Synthesize the key takeaway or mental model of the section in 2–4 sentences.

3. **Save Intermediate JSON**:
   - Write the structured data to a JSON file beside the source file (e.g. `path/to/notes_cornell.json`).
   - Do NOT wrap the JSON file in markdown fences when saving to disk.

4. **Execute Python Formatter**:
   - Run `format_notes.py`:
     ```bash
     python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py /path/to/notes_cornell.json
     ```
   - Optional: Add `--anki` to generate flashcards for spaced repetition:
     ```bash
     python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py /path/to/notes_cornell.json --anki
     ```

5. **Report to User**:
   - Confirm the created HTML file path.
   - Highlight the **Interactive Self-Quiz Mode** (top toolbar toggle that blurs answers until clicked) and A4 print readiness.

---

## Content & Active Recall Guidelines

- **LaTeX Math Escaping**: Always use standard LaTeX syntax inside math delimiters (`$\\omega$`, `$\\frac{A}{B}$`). In JSON strings, use standard JSON escaping (`"\\omega"`). The formatter automatically sanitizes accidental double-escaped backslashes (`\\\\omega` $\\to$ `\\omega`).
- **Cognitive Question Badges**: The formatter automatically detects cognitive types (`definition`, `mechanism`, `comparison`, `formula`, `pitfall`) based on the cue wording.
- **Spaced Repetition Checkboxes**: Each cue row includes three review checkboxes for Leitner-style tracking across review sessions.
- **Obsidian Callouts**: Notes can contain Obsidian-style callouts (`> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!DANGER]`), rendered as distinct accent boxes.
- **Handling Large Files**: For long documents (> 3,000 words), process section-by-section, combining sections into a single coherent JSON document in source order without duplicating boundary headings.

---

## Intermediate JSON Schema

```json
{
  "title": "Topic or Document Title",
  "source": "path/to/original_notes.md",
  "sections": [
    {
      "heading": "Section / Chapter Title",
      "entries": [
        {
          "cue": "Active recall question or prompt?",
          "notes": "Direct answer, explanation, or code snippet."
        },
        {
          "cue": "Compare X and Y",
          "notes": "- X offers high speed but limited capacity.\n- Y offers high capacity but higher latency."
        }
      ],
      "summary": "High-level synthesis capturing the core takeaways of this section."
    }
  ]
}
```

---

## CLI Reference

```bash
# 1. Format notes to HTML with compact Markdown table receipt:
python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py <input.json> --table

# 2. Inspect high-level section outline (cues count + summary preview) without rendering HTML (~60 tokens):
python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py <input.json> --outline [--table] [--limit 5]

# 3. Document statistics without rendering:
python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py <input.json> --stats [--json]

# 4. Generate Anki flashcard TSV (<input_stem>_anki.tsv) with table receipt:
python3 /home/rodri/.gemini/config/skills/cornell-notes/format_notes.py <input.json> --anki --table

# 5. Check SRS status across notes (compact Markdown table / JSON):
python3 /home/rodri/.gemini/config/skills/cornell-notes/srs_review.py status <input.json or folder> --table
python3 /home/rodri/.gemini/config/skills/cornell-notes/srs_review.py status <folder> --json --project title due_today new

# 6. Start an interactive CLI spaced repetition quiz (SM-2: 1-day fail / 3-day pass):
python3 /home/rodri/.gemini/config/skills/cornell-notes/srs_review.py review <input.json>
```
