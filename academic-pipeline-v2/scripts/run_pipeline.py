#!/usr/bin/env python3
"""Contract-only pipeline runner for academic-pipeline-v2.

This file freezes the stage dispatch interface. Stage functions are stubs that
raise NotImplementedError; no stage logic is implemented here.
"""

import argparse
import json
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


def _now():
    return datetime.now(timezone.utc).isoformat()


def _stage_number(name):
    return int(name[-1])


def _write_step(workspace, stage_number, status, started_at, errors=None):
    """Serialize step_NN.json evidence into 05_verify/."""
    errors = errors or []
    step_path = Path(workspace) / "05_verify" / f"step_{stage_number:02d}.json"
    step_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage_number,
        "stage_name": STAGE_NAMES[stage_number],
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "inputs": {"workspace": str(Path(workspace).resolve())},
        "outputs": [],
        "evidence": [],
        "errors": errors,
    }
    step_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return step_path


def stage1(workspace):
    raise NotImplementedError("Stage 1 (ingest) is not implemented in this contract-only snapshot.")


def stage2(workspace):
    raise NotImplementedError("Stage 2 (sift) is not implemented in this contract-only snapshot.")


def stage3(workspace):
    raise NotImplementedError("Stage 3 (structure) is not implemented in this contract-only snapshot.")


def stage4(workspace):
    raise NotImplementedError("Stage 4 (render) is not implemented in this contract-only snapshot.")


def stage5(workspace):
    raise NotImplementedError("Stage 5 (verify) is not implemented in this contract-only snapshot.")


STAGE_FUNCTIONS = {
    1: stage1,
    2: stage2,
    3: stage3,
    4: stage4,
    5: stage5,
}


def _run_one(workspace, stage_number):
    """Run one stage and always write step_NN.json evidence."""
    started_at = _now()
    try:
        STAGE_FUNCTIONS[stage_number](workspace)
    except Exception as exc:  # noqa: BLE001 - serialize any failure as evidence
        _write_step(workspace, stage_number, "failed", started_at, errors=[str(exc)])
        print(
            f"stage{stage_number} ({STAGE_NAMES[stage_number]}): failed - {exc}",
            file=sys.stderr,
        )
        return False

    _write_step(workspace, stage_number, "ok", started_at)
    print(f"stage{stage_number} ({STAGE_NAMES[stage_number]}): ok")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="run_pipeline.py",
        description="Academic Notes Pipeline v2 stage dispatcher (contract only).",
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
