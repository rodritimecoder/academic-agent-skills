#!/usr/bin/env python3
"""Stage dispatcher for academic-pipeline-v2.

Each stage handler imports its lane module(s) lazily, runs them, and merges
their step payloads into ONE ``05_verify/step_NN.json`` evidence file:

    stage1 -> stage1_canvas + stage1_zoom        (one step_01.json)
    stage2 -> stage2_sift                        (one step_02.json)
    stage3 -> stage3_structure                   (one step_03.json)
    stage4 -> render_graph + render_anki +
              render_cornell                     (one step_04.json)
    stage5 -> gates                              (one step_05.json)

A missing lane module never breaks ``--help``: imports happen inside the
handlers only.  Evidence is written on success *and* failure, and the process
exits 0 only when the merged status is ``ok``.  ``--dry-run`` writes nothing.
"""

import argparse
import importlib
import inspect
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STAGE_NAMES = {
    1: "ingest",
    2: "sift",
    3: "structure",
    4: "render",
    5: "verify",
}

STAGE_CHOICES = ["stage1", "stage2", "stage3", "stage4", "stage5", "all"]

VALID_STATUSES = ("ok", "failed", "skipped")

# What each stage really reads, writes and must be checked for.  Derived from
# SKILL.md's stage breakdown and the JSON contracts in contracts/ (and kept in
# step with the lane modules).  ``write_context`` renders these into the
# stage's ``0N_<name>/CONTEXT.md`` before the stage dispatches.
STAGE_CONTRACTS = {
    1: {
        "reads": [
            "Canvas items for weeks 1-12 (canvas-cli)",
            "Zoom recordings: transcripts + slide keyframes only (zoom-recorder)",
            "01_ingest/meta.json (existing constellation nodes, merged)",
        ],
        "writes": [
            "01_ingest/meta.json (contracts/meta.schema.json)",
            "01_ingest/markdown/Week_NN/*.md",
            "01_ingest/transcripts/Week_NN/*.vtt",
            "01_ingest/CONTEXT.md",
        ],
        "checks": [
            "meta.json validates against contracts/meta.schema.json",
            "asset doctor: MIME types and Zoom passcode presence",
            "scope check: weeks 1-12 only",
            "orientation, admin fluff, empty announcements and quiz "
            "administration are dropped before download",
            "full Zoom video is never downloaded",
        ],
    },
    2: {
        "reads": [
            "01_ingest/**/*.md (ingested lecture and tutorial markdown)",
        ],
        "writes": [
            "02_sift/sift_report.json (contracts/sift_report.schema.json)",
            "02_sift/cleaned/**/*.md",
            "02_sift/CONTEXT.md",
        ],
        "checks": [
            "sift_report.json validates against contracts/sift_report.schema.json",
            "every item routes to keep, review or drop",
            "confidence is within 0..1 and honours the classifier floor",
            "duplicate fingerprints are dropped, not reclassified",
            "markdown and KaTeX fences are balanced",
        ],
    },
    3: {
        "reads": [
            "01_ingest/meta.json (contracts/meta.schema.json)",
            "02_sift/sift_report.json (contracts/sift_report.schema.json)",
            "02_sift/cleaned/**/*.md",
        ],
        "writes": [
            "03_structure/<course>/01_weeks/Week_NN/topic.md",
            "03_structure/<course>/01_weeks/Week_NN/tutorial.md",
            "03_structure/<course>/02_index/index.md",
            "03_structure/<course>/03_state/.agent_state.json",
            "03_structure/<course>/03_state/STATE.md",
            "03_structure/CONTEXT.md",
        ],
        "checks": [
            "OKF v0.2 layout: 01_weeks/, 02_index/, 03_state/, _templates/",
            "02_index/index.md lists every week directory",
            "one home per fact: links over copies",
            "no write escapes the workspace root",
        ],
    },
    4: {
        "reads": [
            "01_ingest/meta.json (contracts/meta.schema.json)",
            "02_sift/cleaned/**/*.md",
        ],
        "writes": [
            "04_render/graph.html",
            "04_render/anki.html",
            "04_render/cornell.html",
            "04_render/CONTEXT.md",
        ],
        "checks": [
            "each page is standalone: inline CSS/JS, no external script src",
            "graph nodes match the weeks and nodes in meta.json",
            "links and anchors resolve inside each page",
            "pages open offline and print cleanly",
        ],
    },
    5: {
        "reads": [
            "01_ingest/meta.json",
            "02_sift/**/*.md and 02_sift/sift_report.json",
            "03_structure/<course>/ (01_weeks/, 02_index/index.md)",
            "04_render/graph.html, anki.html, cornell.html",
        ],
        "writes": [
            "05_verify/step_05.json",
            "05_verify/CONTEXT.md",
        ],
        "checks": [
            "gate1_assets: meta.json validates against contracts/meta.schema.json",
            "gate2_sift: markdown/KaTeX balance and confidence floor",
            "gate3_okf: index.md lists every week directory",
            "gate4_render: three standalone HTML pages present",
            "gate5_judge: fresh-context judge accepts the final sample",
        ],
    },
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _stage_number(name):
    return int(name[-1])


def _load_lane(module_name):
    """Import a lane module from this script's directory, lazily."""
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return importlib.import_module(module_name)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _normalise_output(workspace, item):
    """Coerce one lane output entry into a workspace-relative POSIX path string.

    Lanes have historically emitted absolute paths and, for cornell, a dict
    ``{"path": ..., "kind": ..., "bytes": ...}``.  The step contract wants a
    flat array of workspace-relative path strings, so both shapes collapse to
    the path.  Unusable entries return ``None``.
    """
    if isinstance(item, dict):
        item = item.get("path")
    if not isinstance(item, (str, Path)):
        return None
    text = str(item).strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        root = Path(workspace).resolve()
        try:
            path = path.resolve().relative_to(root)
        except (OSError, ValueError):
            try:
                path = Path(os.path.relpath(path, root))
            except (OSError, ValueError):
                return None
    return path.as_posix()


def _normalise_outputs(workspace, items):
    """Return sorted, deduplicated workspace-relative path strings."""
    normalised = set()
    for item in items:
        rel = _normalise_output(workspace, item)
        if rel is not None:
            normalised.add(rel)
    return sorted(normalised)


def _merge_results(stage_number, started_at, parts, workspace=None):
    """Merge ``[(lane_name, payload_or_exception_text)]`` into one step payload.

    Every merged stage reports ``outputs`` as workspace-relative path strings,
    deduplicated and sorted (see :func:`_normalise_outputs`).

    Status: ``ok`` if any lane ran ok, ``skipped`` if every lane skipped,
    ``failed`` otherwise (including a lane that raised).  Stage 5 is stricter:
    a skipped gate (e.g. the missing fresh-context judge) can never be merged
    into ``ok``, so a missing check never looks green.
    """
    statuses = []
    outputs = []
    evidence = []
    errors = []
    lanes = {}
    extras = {}

    for name, result in parts:
        if not isinstance(result, dict):
            statuses.append("failed")
            errors.append(f"{name}: {result}")
            continue
        status = str(result.get("status") or "failed")
        statuses.append(status if status in VALID_STATUSES else "failed")
        if isinstance(result.get("inputs"), dict):
            lanes[name] = result["inputs"]
        outputs.extend(_as_list(result.get("outputs")))
        evidence.extend(_as_list(result.get("evidence")))
        errors.extend(str(item) for item in _as_list(result.get("errors")))
        for key, value in result.items():
            if key in ("gates", "facts", "details"):
                extras[key] = value

    if stage_number == 5:
        # A missing judge dependency must never look green: skip wins over ok.
        if "failed" in statuses:
            status = "failed"
        elif "skipped" in statuses:
            status = "skipped"
        elif statuses:
            status = "ok"
        else:
            status = "skipped"
    elif "ok" in statuses:
        status = "ok"
    elif statuses and all(item == "skipped" for item in statuses):
        status = "skipped"
    else:
        status = "failed"

    payload = {
        "stage": stage_number,
        "stage_name": STAGE_NAMES[stage_number],
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "inputs": {"lanes": lanes},
        "outputs": _normalise_outputs(workspace, outputs),
        "evidence": evidence,
        "errors": errors,
    }
    payload.update(extras)
    return payload


def _write_step(workspace, stage_number, payload):
    """Serialize a merged step payload into 05_verify/step_NN.json."""
    step_path = Path(workspace) / "05_verify" / f"step_{stage_number:02d}.json"
    step_path.parent.mkdir(parents=True, exist_ok=True)
    step_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return step_path


def _accepts(run, name):
    try:
        params = inspect.signature(run).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins/C callables
        return False
    if name in params:
        return True
    return any(p.kind is p.VAR_KEYWORD for p in params.values())


def _call(module_name, workspace, dry_run, deps=None, **kwargs):
    """Run one lane module, returning its payload (exceptions become text)."""
    try:
        module = _load_lane(module_name)
    except Exception as exc:  # noqa: BLE001 - a missing module is step evidence
        return f"cannot import {module_name}: {exc}"
    run = getattr(module, "run", None)
    if not callable(run):
        return f"{module_name}.run is not callable"

    call_kwargs = dict(kwargs)
    if _accepts(run, "dry_run"):
        call_kwargs["dry_run"] = dry_run
    elif dry_run:
        # The lane has no dry-run switch: never let it write during --dry-run.
        return {
            "status": "skipped",
            "outputs": [],
            "evidence": [f"{module_name}: skipped (no dry-run support)"],
            "errors": [],
        }
    if _accepts(run, "deps"):
        call_kwargs["deps"] = deps

    try:
        return run(workspace, **call_kwargs)
    except Exception as exc:  # noqa: BLE001 - serialize as evidence
        return f"{module_name}.run raised: {exc}"


def _run_lanes(workspace, dry_run, lanes):
    """Run ``[(name, kwargs)]`` and return merged payload parts."""
    parts = []
    for name, kwargs in lanes:
        parts.append((name, _call(name, workspace, dry_run, **kwargs)))
    return parts


def _write_stage_context(workspace, stage_number, dry_run):
    """Write ``0N_<name>/CONTEXT.md`` before the stage dispatches.

    ``--dry-run`` must leave the workspace untouched, so it writes nothing.
    Re-runs refresh the file (``overwrite=True``) rather than failing on the
    CONTEXT.md left by a previous run.
    """
    if dry_run:
        return None
    contract = STAGE_CONTRACTS[stage_number]
    module = _load_lane("write_context")
    return module.write_stage_context(
        workspace,
        stage_number,
        reads=contract["reads"],
        writes=contract["writes"],
        checks=contract["checks"],
        overwrite=True,
    )


def stage1(workspace, dry_run=False):
    _write_stage_context(workspace, 1, dry_run)
    return _run_lanes(
        workspace,
        dry_run,
        [("stage1_canvas", {}), ("stage1_zoom", {})],
    )


def stage2(workspace, dry_run=False):
    _write_stage_context(workspace, 2, dry_run)
    return _run_lanes(workspace, dry_run, [("stage2_sift", {})])


def stage3(workspace, dry_run=False):
    _write_stage_context(workspace, 3, dry_run)
    return _run_lanes(workspace, dry_run, [("stage3_structure", {})])


def stage4(workspace, dry_run=False):
    _write_stage_context(workspace, 4, dry_run)
    return _run_lanes(
        workspace,
        dry_run,
        [("render_graph", {}), ("render_anki", {}), ("render_cornell", {})],
    )


def stage5(workspace, dry_run=False):
    _write_stage_context(workspace, 5, dry_run)
    return _run_lanes(workspace, dry_run, [("gates", {})])


STAGE_FUNCTIONS = {
    1: stage1,
    2: stage2,
    3: stage3,
    4: stage4,
    5: stage5,
}


def _run_one(workspace, stage_number, dry_run=False):
    """Run one stage and always write step_NN.json evidence (unless dry run)."""
    started_at = _now()
    try:
        parts = STAGE_FUNCTIONS[stage_number](workspace, dry_run=dry_run)
        payload = _merge_results(stage_number, started_at, parts, workspace=workspace)
    except Exception as exc:  # noqa: BLE001 - serialize any failure as evidence
        payload = {
            "stage": stage_number,
            "stage_name": STAGE_NAMES[stage_number],
            "status": "failed",
            "started_at": started_at,
            "finished_at": _now(),
            "inputs": {"workspace": str(Path(workspace).resolve())},
            "outputs": [],
            "evidence": [],
            "errors": [str(exc)],
        }

    if not dry_run:
        try:
            _write_step(workspace, stage_number, payload)
        except OSError as exc:
            payload["status"] = "failed"
            payload["errors"] = list(payload.get("errors") or []) + [
                f"cannot write step file: {exc}"
            ]

    status = payload["status"]
    message = (
        f"stage{stage_number} ({STAGE_NAMES[stage_number]}): {status}"
    )
    if status == "ok":
        print(message)
    else:
        detail = "; ".join(payload.get("errors") or [])
        print(f"{message}{' - ' + detail if detail else ''}", file=sys.stderr)
    return status == "ok"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="Academic Notes Pipeline v2 stage dispatcher.",
    )
    parser.add_argument(
        "stage",
        choices=STAGE_CHOICES,
        help="stage to run: stage1..stage5, or all",
    )
    parser.add_argument(
        "--workspace",
        default="./workspace",
        help="course workspace directory (default: ./workspace)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the stages that would run without dispatching or writing evidence",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    if not workspace.is_dir():
        parser.error(f"workspace does not exist: {workspace}")

    if args.stage == "all":
        stage_numbers = [1, 2, 3, 4, 5]
    else:
        stage_numbers = [_stage_number(args.stage)]

    if args.dry_run:
        for number in stage_numbers:
            print(f"would run stage{number} ({STAGE_NAMES[number]}) in {workspace}")
        return 0

    for number in stage_numbers:
        if not _run_one(workspace, number):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
