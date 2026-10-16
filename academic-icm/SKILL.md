---
name: academic-icm
description: >
  Unified Academic ICM (Interpretable Context Methodology) Suite & Orchestrator. Unifies Canvas LMS
  ingestion (canvas-cli), Zoom cloud lecture & slide extraction (zoom-recorder), active-recall Cornell
  notes (cornell-notes), and OKF curriculum architecture into a single late-binding academic hub.
---

# Academic ICM (`academic-icm`)

> **Unified Academic Intelligence Suite & ICM Pipeline Orchestrator for University Knowledge Workspaces.**  
> Solves the seam between raw Canvas LMS downloads, Zoom lecture recordings, Markdown conversions, Cornell study sheets, and the OKF Knowledge Cosmos graph.

---

## 🏛️ Integrated Academic Modules & Commands

`academic-icm` serves as the single late-binding hub for all university academic workflows:

```bash
# 1. Canvas LMS API Integration (courses, assignments, grades, modules, announcements)
academic-icm canvas courses --summary
academic-icm canvas modules <course_id>
# Or via backward-compatible shim: canvas-cli ...

# 2. Zoom Cloud Recording & Slide Keyframe Extraction
academic-icm zoom --url <zoom_rec_url> [--passcode <code>] [--keyframes] [--ocr]
# Or via backward-compatible shim: zoom-recorder ...

# 3. Active-Recall Cornell Notes HTML & Anki TSV Generation
academic-icm cornell <notes_cornell.json> [--anki]
# Or via backward-compatible shim: cornell-notes ...

# 4. Spaced Repetition (SRS) Review Engine
academic-icm srs review <notes_cornell.json>

# 5. List Integrated Modules & Rubrics
academic-icm modules
```

---

## 🏛️ The 4 Invariants of Academic ICM

1. **Strict Stem Inheritance (No Creative Renaming)**:
   - When generating Cornell notes from a source Markdown note, the output stem **must** match the source Markdown file stem:
     - Source: `Week_1/markdown/48520_topic_1_and_2.md`
     - Output JSON: `outputs/json/48520_topic_1_and_2_cornell.json`
     - Output HTML: `outputs/html/48520_topic_1_and_2_cornell.html`
     - Output Anki: `outputs/anki/48520_topic_1_and_2_anki.tsv`
2. **Explicit Source Linkage**:
   - Every `_cornell.json` must record `"source": "<rel_path_to_markdown>"` so the curriculum compiler can link by path fallback.
3. **Curated Curriculum Hierarchy**:
   - `CURRICULUM_TREE.md` defines the virtual chronological outline (`Week 01 → Week 02 → ...`). Prune administrative noise (empty links, welcome announcements) so the Knowledge Cosmos reflects actual learning milestones.
4. **Single-Command Verification**:
   - `academic-icm status` and `academic-icm audit` detect coverage gaps, orphaned notes, and broken links before deployment.

---

## 🚀 CLI Commands

### 1. Check Coverage & Detect Orphans
```bash
academic-icm status
# or target a specific vault
academic-icm status /run/media/rodri/AI/University/notes
```
Prints curriculum coverage table by subject, total card count, and lists orphaned notes.

### 2. Scaffold a New Note from Markdown
```bash
# Auto-generates matching _cornell.json template with pre-filled source and inherited stem
academic-icm scaffold "48520 - Electronics and Circuits/Week_2/markdown/week_2_topic_notes.md"
```

### 3. Build HTML & Anki TSV from JSON
```bash
academic-icm build-note "48520 - Electronics and Circuits/outputs/json/week_2_topic_notes_cornell.json"
```

### 4. Deep Audit & Linting
```bash
academic-icm audit
```
Verifies stem alignment, minimum cue depth (6–8 cues), LaTeX formula delimiters (`$$...$$` or `$...$`), and HTML/TSV synchronization.

### 5. Recompile Knowledge Cosmos & Study Portal
```bash
academic-icm compile
```
Compiles `CURRICULUM_TREE.md` into:
- **`viz.html`**: Dual-Mode Knowledge Cosmos (`📅 Canvas Constellations` ⟷ `🌌 Semantic Web`).
- **`cornell_index.html`**: Active-recall study portal with self-quiz launch buttons.

### 6. Repair Known Stem Drift
```bash
academic-icm sync-orphans
```
Renames and aligns historical stem mismatches so previously unlinked notes attach to the graph.

### 7. Launch Local Study Portal Server
```bash
academic-icm serve --port 8765
```
Previews the interactive portal and D3 Cosmos at `http://localhost:8765/`.
