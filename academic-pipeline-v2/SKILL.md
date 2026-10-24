---
name: academic-pipeline-v2
description: >
  Academic Notes Pipeline (v2). Text-first university ingestion (Canvas + Zoom) →
  parallel classifier sifting (jev-decision, eval-router, free-swarm) → OKF v0.2
  curriculum structuring → three focused HTML outputs (constellation graph.html,
  anki.html, and cornell.html) with micro-gates at every stage.
  Supersedes monolithic academic-icm.
compatibility: "Requires canvas-cli, zoom-recorder, markitdown-cli, and local inference (:8080, :8083)."
allowed-tools: "Bash(canvas-cli:*) Bash(zoom-recorder:*) Bash(markitdown:*) Bash(jev:*) Read Write"
---

# Academic Notes Pipeline v2 (`academic-pipeline-v2`)

> **Text-first university lecture & tutorial pipeline.**  
> Ingests Canvas + Zoom, sifts early via parallel classifiers, structures into OKF v0.2 / ICM folders, and renders three clean, single-purpose HTML outputs.  
> **Supersedes v1 `academic-icm`.**

---

## 🏛️ Core Principles

1. **Clean upstream, render downstream.** The poison sits upstream. Sift out admin/fluff/duplicates before writing to disk.
2. **Three focused outputs over one monolith.** Replace the old mega-page (`viz.html` / `study.html`) with 3 standalone, decoupled targets:
   - **`graph.html`** — Minimal **constellation view** (Canvas-aligned radial layout: course → week → topic/solution with node settings panel).
   - **`anki.html`** — **Anki full hub**: deck management, card review, flip/reveal, progress, import/export TSV.
   - **`cornell.html`** — Clean white **Cornell study sheet**: active-recall cue-note pairs, self-quiz toggle, print-ready.
3. **Code decides wherever it can.** Deterministic filters (empty links, file-size bounds, week scopes) in code; models judge ambiguity.
4. **A gate at every stage.** Micro-gates exit non-zero with serialized evidence (`step_NN.json`). "Always run the control."

---

## 📁 The 5 Pipeline Stages (ICM Workspace)

```
<course_workspace>/
├── AGENTS.md             # Root workspace routing (< 60 lines)
├── CONTEXT.md            # Stage execution map & status
├── 01_ingest/            # Smart Canvas + Zoom ingestion (relevant notes only)
│   ├── CONTEXT.md
│   ├── markdown/         # Extracted lecture & tutorial text
│   ├── transcripts/      # Zoom VTT & ASR transcripts
│   └── meta.json         # Constellation node metadata
├── 02_sift/              # Classifier triage & deduplication
│   ├── CONTEXT.md
│   ├── sift_report.json  # Classifier decisions & confidence
│   └── cleaned/          # Filtered, tagged, deduped notes
├── 03_structure/         # OKF v0.2 curriculum layout
│   ├── CONTEXT.md
│   ├── 01_weeks/         # Week_01 to Week_12 (topic.md, tutorial.md)
│   ├── 02_index/         # Generated OKF maps (never hand-edited)
│   └── 03_state/         # .agent_state.json & STATE.md
├── 04_render/            # Three standalone HTML targets
│   ├── CONTEXT.md
│   ├── graph.html        # Constellation view
│   ├── anki.html         # Anki review hub
│   └── cornell.html      # Cornell notes sheet
└── 05_verify/            # Independent verification & gates
    ├── CONTEXT.md
    └── step_*.json       # Serialized evidence logs
```

---

## 🛠️ Stage Breakdown & Tooling

### Stage 1: Smart Ingestion (`01_ingest`)
* **Spine:** Feeds the constellation view directly. Only downloads what the graph needs.
* **Tools:** `canvas-cli`, `zoom-recorder`, `markitdown-cli`.
* **Two Streams Per Week:**
  1. *Topic notes* (lecture slides, pages, PDFs).
  2. *Tutorial solutions* (worked problems).
* **Smart Filter:** Light classifier (`jev bool`) triages Canvas items by title *before download*. Skips orientation, admin fluff, empty announcements, and quiz administration. Zoom downloads transcripts/keyframes only (never full video).

### Stage 2: Sifting (`02_sift`)
* **Parallel Classifiers:** Combines local models with `openrouter-free` subagents (`free-swarm`), cached via `semantic-cache`.
* **Triage Tasks:**
  - `is_admin_fluff` — drops non-academic items.
  - `is_duplicate` — signature fingerprint deduplication.
  - `topic_tag` — extracts graph edge relationships.
  - `quality_score` (0.0–1.0) — low confidence routed to review queue.

### Stage 3: Structuring (`03_structure`)
* **Spec:** Adheres to **Open Knowledge Format (OKF v0.2)** via `okf-architect`.
* **State Ledger:** Compaction via `state-compactor`; context slicing via `cgate`.
* **Invariants:** One home per fact (links over copies); filesystem encodes state.

### Stage 4: Render (`04_render`)
* Generates the 3 independent HTML surfaces without cross-page coupling.
* Standalone files; can be viewed locally or exposed via `tailscale serve`.

### Stage 5: Verification Micro-Gates (`05_verify`)
* **Stage 1 Gate `[D]`:** Asset doctor (MIME types, Zoom passcode presence, scope check weeks 1–12).
* **Stage 2 Gate `[D]+[P]`:** KaTeX / Markdown balance check, classifier confidence floor.
* **Stage 3 Gate `[D]`:** OKF v0.2 schema check, one-home-per-fact audit, STALE mtime checks.
* **Stage 4 Gate `[D]`:** Render smoke (valid DOM, zero console errors, template sanity).
* **Stage 5 Gate `[P]`:** Fresh-context unbiased judge (`jev-decision`) accepts final sample.
