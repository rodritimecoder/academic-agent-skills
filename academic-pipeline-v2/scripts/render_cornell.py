#!/usr/bin/env python3
"""Stage 4c - render the Cornell notes sheet as ONE standalone HTML file.

Input:  ``workspace/02_sift/cleaned`` (markdown notes).
Output: ``workspace/04_render/cornell.html`` - offline, print-ready white sheet
        with cue/note pairs (cue = heading, note = paragraph), a self-quiz
        toggle that hides the notes, and ``@media print`` rules.

All external effect goes through ``deps`` (dict of callables) so the stage can
be driven by fakes.  The stage never raises: every outcome is serialized as a
step payload valid against ``contracts/step.schema.json``.
"""

import html
import re
from datetime import datetime, timezone
from pathlib import Path

STAGE = 4
STAGE_NAME = "render-cornell"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_BULLET_RE = re.compile(r"^[-*+]\s+")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _payload(status, started_at, inputs=None, outputs=None, evidence=None, errors=None):
    return {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "inputs": inputs or {},
        "outputs": outputs or [],
        "evidence": evidence or [],
        "errors": errors or [],
    }


def default_list_notes(cleaned_dir):
    """All markdown notes under ``02_sift/cleaned`` (sorted, deterministic)."""
    cleaned_dir = Path(cleaned_dir)
    if not cleaned_dir.is_dir():
        return []
    return sorted(p for p in cleaned_dir.rglob("*.md") if p.is_file())


def default_read_note(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def default_write_html(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


DEFAULT_DEPS = {
    "list_notes": default_list_notes,
    "read_note": default_read_note,
    "write_html": default_write_html,
}


def parse_pairs(text):
    """Split markdown into (cue, note) pairs: cue = heading, note = paragraph(s)."""
    pairs = []
    cue = None
    buf = []

    def flush():
        if cue is not None:
            pairs.append({"cue": cue, "note": " ".join(buf).strip()})
        del buf[:]

    in_fence = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        heading = None if in_fence else _HEADING_RE.match(stripped)
        if heading:
            flush()
            cue = heading.group(2).strip()
            continue
        if not stripped or cue is None:
            continue
        buf.append(_BULLET_RE.sub("", stripped))
    flush()
    return pairs


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --ink: #111318; --rule: #c9ced8; --cue: #1f3a8a; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: #ffffff; color: var(--ink); }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    font-size: 15px;
    line-height: 1.55;
    padding: 32px 24px 64px;
    max-width: 1000px;
    margin: 0 auto;
  }}
  header.sheet-head {{
    border-bottom: 2px solid var(--ink);
    padding-bottom: 14px;
    margin-bottom: 22px;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }}
  header.sheet-head h1 {{ font-size: 22px; margin: 0; letter-spacing: -0.01em; }}
  header.sheet-head .meta {{ font-size: 12px; color: #5b6373; }}
  .quiz-toggle {{
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    padding: 7px 14px;
    border: 1px solid var(--ink);
    border-radius: 6px;
    background: #ffffff;
    color: var(--ink);
    cursor: pointer;
  }}
  .quiz-toggle:focus-visible {{ outline: 2px solid var(--cue); outline-offset: 2px; }}
  .pair {{
    display: grid;
    grid-template-columns: minmax(180px, 30%) 1fr;
    border-bottom: 1px solid var(--rule);
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .cue {{ border-right: 1px solid var(--rule); padding: 14px 16px 14px 0; }}
  .cue h2 {{ font-size: 15px; font-weight: 700; color: var(--cue); margin: 0; cursor: pointer; }}
  .note {{ padding: 14px 0 14px 16px; }}
  .note p {{ margin: 0; }}
  body.quiz-on .note {{ visibility: hidden; }}
  body.quiz-on .pair.revealed .note {{ visibility: visible; }}
  body.quiz-on .pair.revealed .cue h2 {{ color: #5b6373; }}
  .hint {{ font-size: 12px; color: #5b6373; margin-top: 18px; }}
  .empty {{ font-size: 14px; color: #5b6373; }}
  @media print {{
    @page {{ margin: 16mm; }}
    html, body {{ background: #ffffff; color: #000000; }}
    body {{ padding: 0; max-width: none; font-size: 11pt; }}
    .quiz-toggle, .hint {{ display: none; }}
    body.quiz-on .note, body.quiz-on .pair.revealed .note {{ visibility: visible; }}
    .pair {{ grid-template-columns: 32% 1fr; }}
    .cue h2 {{ color: #000000; }}
  }}
</style>
</head>
<body class="sheet">
<header class="sheet-head">
  <h1>{title}</h1>
  <span class="meta">{pair_count} cue/note pairs</span>
  <button type="button" class="quiz-toggle" id="quizToggle" aria-pressed="false">Self-quiz: off</button>
</header>
<main class="sheet-body">
{pairs}
</main>
<p class="hint">Self-quiz hides the notes &mdash; click a cue to reveal its note.</p>
<script>
  (function () {{
    var btn = document.getElementById("quizToggle");
    var body = document.body;
    if (!btn) return;
    btn.addEventListener("click", function () {{
      var on = body.classList.toggle("quiz-on");
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = on ? "Self-quiz: on" : "Self-quiz: off";
      if (!on) {{
        var open = document.querySelectorAll(".pair.revealed");
        for (var i = 0; i < open.length; i++) open[i].classList.remove("revealed");
      }}
    }});
    body.addEventListener("click", function (ev) {{
      var cue = ev.target.closest ? ev.target.closest(".cue") : null;
      if (!cue || !body.classList.contains("quiz-on")) return;
      if (cue.parentNode && cue.parentNode.classList) cue.parentNode.classList.toggle("revealed");
    }});
  }})();
</script>
</body>
</html>
"""


def _render_pairs(pairs):
    if not pairs:
        return '<p class="empty">No cue/note pairs found in 02_sift/cleaned.</p>'
    chunks = []
    for index, pair in enumerate(pairs, start=1):
        cue = html.escape(pair["cue"])
        note = html.escape(pair["note"]) or "&nbsp;"
        chunks.append(
            '<section class="pair" data-index="%d">'
            '<div class="cue"><h2>%s</h2></div>'
            '<div class="note"><p>%s</p></div>'
            "</section>" % (index, cue, note)
        )
    return "\n".join(chunks)


def render_html(pairs, title="Cornell Notes"):
    return _PAGE.format(
        title=html.escape(title),
        pair_count=len(pairs),
        pairs=_render_pairs(pairs),
    )


def run(workspace: Path, dry_run: bool = False, deps: dict | None = None) -> dict:
    started_at = _now()
    workspace = Path(workspace)
    cleaned_dir = workspace / "02_sift" / "cleaned"
    out_path = workspace / "04_render" / "cornell.html"
    inputs = {"cleaned_dir": str(cleaned_dir), "dry_run": bool(dry_run)}

    resolved = dict(DEFAULT_DEPS) if deps is None else dict(deps)
    missing = [key for key in DEFAULT_DEPS if not callable(resolved.get(key))]
    if missing:
        return _payload(
            "skipped",
            started_at,
            inputs=inputs,
            evidence=[{"check": "deps", "missing": missing}],
        )

    try:
        note_paths = list(resolved["list_notes"](cleaned_dir) or [])
        if not note_paths:
            return _payload(
                "skipped",
                started_at,
                inputs=inputs,
                evidence=[{"check": "inputs", "reason": "no cleaned notes found"}],
            )

        pairs = []
        used = []
        for note_path in sorted(note_paths, key=str):
            pairs.extend(parse_pairs(resolved["read_note"](note_path) or ""))
            used.append(str(note_path))

        inputs["notes"] = used
        page = render_html(pairs)

        if dry_run:
            return _payload(
                "ok",
                started_at,
                inputs=inputs,
                evidence=[
                    {"check": "dry_run", "target": str(out_path), "pair_count": len(pairs)},
                ],
            )

        resolved["write_html"](out_path, page)
        size = out_path.stat().st_size if out_path.exists() else len(page.encode("utf-8"))
        return _payload(
            "ok",
            started_at,
            inputs=inputs,
            outputs=[{"path": str(out_path), "kind": "html", "bytes": size}],
            evidence=[
                {"check": "cornell_pairs", "pair_count": len(pairs)},
                {"check": "size_bytes", "bytes": size},
            ],
        )
    except Exception as exc:  # noqa: BLE001 - serialize any failure as evidence
        return _payload("failed", started_at, inputs=inputs, errors=[str(exc)])


if __name__ == "__main__":
    import json
    import sys

    result = run(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(json.dumps(result, indent=2))
