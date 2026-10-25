#!/usr/bin/env python3
"""Write a per-stage CONTEXT.md into each working folder.

ICM expects a ``CONTEXT.md`` in every working folder: what it reads, what it
does, what it writes, and what a human must check.  No stage of this pipeline
wrote one, so this module fills the gap.

It renders ``_templates/CONTEXT.md`` (inline fallback if that file is absent)
into ``workspace/0N_<name>/CONTEXT.md`` for stages 1-5, substituting
``{{STAGE}}``, ``{{TITLE}}``, ``{{READS}}``, ``{{WRITES}}``, ``{{CHECKS}}``
and ``{{HUMAN}}``.

Public API
----------
write_stage_context(workspace, stage, *, reads, writes, checks, human="",
                    overwrite=False) -> Path
run(workspace, dry_run=False, deps=None) -> dict   # step.schema.json payload

CLI
---
    python write_context.py WORKSPACE [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Stage folder + title, kept local so the script runs standalone.
STAGES = {
    1: ("01_ingest", "Ingest"),
    2: ("02_sift", "Sift"),
    3: ("03_structure", "Structure"),
    4: ("04_render", "Render"),
    5: ("05_verify", "Verify"),
}

TEMPLATE_RELPATH = Path("_templates") / "CONTEXT.md"

INLINE_TEMPLATE = """# CONTEXT - Stage {{STAGE}}: {{TITLE}}

Folder: `0{{STAGE}}_{{TITLE}}`

## Reads
{{READS}}

## Does
- Produces the artefacts for stage {{STAGE}} of the academic pipeline.
- Records every input it used so the step can be replayed.

## Writes
{{WRITES}}

## Human checks
{{CHECKS}}

Human sign-off: {{HUMAN}}
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _bullet(items):
    """Render a list of strings as a markdown bullet list."""
    if isinstance(items, str):
        items = [items]
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return "- _none_"
    return "\n".join(f"- `{i}`" for i in items)


def stage_dir_name(stage):
    stage = int(stage)
    if stage not in STAGES:
        raise ValueError(f"stage must be one of 1-5, got {stage!r}")
    return STAGES[stage][0]


def stage_title(stage):
    stage = int(stage)
    if stage not in STAGES:
        raise ValueError(f"stage must be one of 1-5, got {stage!r}")
    return STAGES[stage][1]


def _find_template(workspace):
    """Locate _templates/CONTEXT.md: inside the workspace, then beside it."""
    candidates = [
        Path(workspace) / TEMPLATE_RELPATH,
        Path(__file__).resolve().parent.parent / TEMPLATE_RELPATH,
        Path(__file__).resolve().parent / TEMPLATE_RELPATH,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def render_context(template_text, stage, title, reads, writes, checks, human=""):
    """Substitute the six placeholders; keep stage facts in the body always."""
    folder = stage_dir_name(stage)
    human = (human or "").strip() or "_to be confirmed by the researcher_"

    replacements = {
        "{{STAGE}}": str(stage),
        "{{TITLE}}": title,
        "{{FOLDER}}": folder,
        "{{COURSE}}": f"stage {stage} ({title})",
        "{{READS}}": _bullet(reads),
        "{{WRITES}}": _bullet(writes),
        "{{CHECKS}}": _bullet(checks),
        "{{HUMAN}}": human,
    }

    text = template_text
    had_stage = "{{STAGE}}" in text
    had_sections = "{{READS}}" in text or "{{WRITES}}" in text
    for key, value in replacements.items():
        text = text.replace(key, value)

    parts = []
    if not had_stage:
        parts.append(f"# CONTEXT - Stage {stage}: {title}\n\nFolder: `{folder}`")
    body = text.rstrip("\n")
    # The template opens with its own H1; this file already has a stage heading.
    if body.lstrip().startswith("# "):
        body = "\n".join(body.splitlines()[1:]).lstrip("\n")
    parts.append(body)
    if not had_sections:
        parts.append(
            "## Reads\n"
            f"{_bullet(reads)}\n\n"
            "## Writes\n"
            f"{_bullet(writes)}\n\n"
            "## Human checks\n"
            f"{_bullet(checks)}\n\n"
            f"Human sign-off: {human}"
        )
    body = "\n\n".join(parts)
    if not body.endswith("\n"):
        body += "\n"
    return body


def write_stage_context(
    workspace,
    stage,
    *,
    reads,
    writes,
    checks,
    human="",
    overwrite=False,
):
    """Render CONTEXT.md into ``workspace/0N_<name>/CONTEXT.md``.

    Refuses to clobber an existing file unless ``overwrite=True``.
    Returns the Path written.
    """
    workspace = Path(workspace)
    stage = int(stage)
    folder = stage_dir_name(stage)
    title = stage_title(stage)

    target_dir = workspace / folder
    target = target_dir / "CONTEXT.md"

    if target.exists() and not overwrite:
        raise FileExistsError(
            f"{target} already exists; pass overwrite=True to replace it"
        )

    tmpl = _find_template(workspace)
    template_text = tmpl.read_text(encoding="utf-8") if tmpl else INLINE_TEMPLATE

    body = render_context(template_text, stage, title, reads, writes, checks, human)

    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


# --------------------------------------------------------------------------
# Step-runner entry point (payload valid against contracts/step.schema.json)
# --------------------------------------------------------------------------
def default_spec(stage):
    """Default reads/writes/checks for one stage, used by ``run``."""
    folder = stage_dir_name(stage)
    reads = {
        1: [f"{folder}/TASK.md", "inputs/ (canvas export, zoom recordings)"],
        2: ["01_ingest/meta.json", "01_ingest/*.md"],
        3: ["01_ingest/meta.json", "02_sift/ (cleaned notes, sift_report.json)"],
        4: ["03_structure/<course>/02_index/index.md", "03_structure/<course>/01_weeks/"],
        5: ["03_structure/<course>/", "04_render/ (graph, anki, cornell)"],
    }[stage]
    writes = {
        1: ["01_ingest/meta.json", "01_ingest/*.md"],
        2: ["02_sift/*.md", "02_sift/sift_report.json"],
        3: ["03_structure/<course>/01_weeks/", "03_structure/<course>/02_index/index.md"],
        4: ["04_render/graph.html", "04_render/anki.html", "04_render/cornell.html"],
        5: ["05_verify/step_05.json", "05_verify/gate_report.json"],
    }[stage]
    checks = {
        1: ["meta.json validates against contracts/meta.schema.json"],
        2: ["every note carries a source pointer"],
        3: ["each week has slides/notes/cornell entries"],
        4: ["rendered HTML opens and links resolve"],
        5: ["all gates report ok"],
    }[stage]
    return {
        "reads": reads,
        "writes": writes + [f"{folder}/CONTEXT.md"],
        "checks": checks + ["CONTEXT.md lists reads, writes and human checks"],
        "human": "Confirm scope and listed reads before running the stage.",
    }


def run(workspace, dry_run=False, deps=None):
    """Write CONTEXT.md for stages 1-5; return a step.schema.json payload."""
    workspace = Path(workspace)
    started_at = _now()
    outputs = []
    evidence = []
    errors = []

    for stage in sorted(STAGES):
        spec = default_spec(stage)
        target = workspace / stage_dir_name(stage) / "CONTEXT.md"
        try:
            if target.exists():
                outputs.append(str(target))
                evidence.append(f"stage{stage}: context kept (already present)")
                continue
            if dry_run:
                outputs.append(str(target))
                evidence.append(f"stage{stage}: would write {target}")
                continue
            path = write_stage_context(
                workspace,
                stage,
                reads=spec["reads"],
                writes=spec["writes"],
                checks=spec["checks"],
                human=spec["human"],
                overwrite=False,
            )
            outputs.append(str(path))
            evidence.append(f"stage{stage}: wrote {path}")
        except Exception as exc:  # noqa: BLE001 - serialize as step evidence
            errors.append(f"stage{stage}: {exc}")
            evidence.append(f"stage{stage}: failed - {exc}")

    missing = [
        str(workspace / stage_dir_name(s) / "CONTEXT.md")
        for s in sorted(STAGES)
        if not (workspace / stage_dir_name(s) / "CONTEXT.md").is_file()
    ]
    status = "ok" if not errors and not missing else "failed"
    if dry_run and not errors:
        status = "ok"

    return {
        "stage": 5,
        "stage_name": "verify",
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "inputs": {
            "workspace": str(workspace),
            "template": str(_find_template(workspace) or "<inline fallback>"),
            "dry_run": bool(dry_run),
        },
        "outputs": outputs,
        "evidence": evidence,
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write per-stage CONTEXT.md files")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    payload = run(args.workspace, dry_run=args.dry_run)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
