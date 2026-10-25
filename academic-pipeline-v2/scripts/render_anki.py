#!/usr/bin/env python3
"""Stage 4b: render an offline Anki-style review hub.

Reads workspace/02_sift/cleaned/**/*.md and emits ONE standalone
workspace/04_render/anki.html with inline CSS/JS (no external script src).

- one deck per week directory (immediate child of 02_sift/cleaned); a flat
  notes tree gets a single "all" deck
- one card per markdown heading: question = heading text,
  answer = first paragraph under that heading
- card review with flip, next/prev and a reviewed/total counter
- client-side TSV export and import

Usage:
    python scripts/render_anki.py --workspace ./workspace
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STAGE = 4
STAGE_NAME = "render"
DEFAULT_DECK = "all"


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def _heading_text(line):
    return line.lstrip().lstrip("#").strip()


def extract_cards(text):
    """Return [{'q': str, 'a': str}] - one card per markdown heading."""
    cards = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("#"):
            continue
        question = _heading_text(line)
        if not question:
            continue
        answer_lines = []
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        while j < len(lines) and lines[j].strip() and not lines[j].lstrip().startswith("#"):
            answer_lines.append(lines[j].strip())
            j += 1
        cards.append({"q": question, "a": " ".join(answer_lines)})
    return cards


def _deck_name(cleaned, path):
    try:
        rel = path.relative_to(cleaned)
    except ValueError:
        return DEFAULT_DECK
    return rel.parts[0] if len(rel.parts) > 1 else DEFAULT_DECK


def collect(cleaned):
    """Return ordered decks: [{'name': str, 'cards': [...]}]."""
    cleaned = Path(cleaned)
    if not cleaned.is_dir():
        return []
    decks, order = {}, []
    for path in sorted(cleaned.rglob("*.md")):
        if not path.is_file():
            continue
        name = _deck_name(cleaned, path)
        if name not in decks:
            decks[name] = []
            order.append(name)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        source = str(path.relative_to(cleaned))
        for card in extract_cards(text):
            card["src"] = source
            decks[name].append(card)
    order.sort(key=lambda n: (n == DEFAULT_DECK, n))
    return [{"name": n, "cards": decks[n]} for n in order if decks[n]]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anki Hub</title>
<style>
:root{--bg:#0f1216;--panel:#171c23;--line:#2a323d;--fg:#e6edf3;--dim:#8b98a5;--acc:#4da3ff}
*{box-sizing:border-box}
body{margin:0;font:16px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--fg)}
header{padding:16px 20px;border-bottom:1px solid var(--line);display:flex;gap:16px;flex-wrap:wrap;align-items:center}
h1{font-size:18px;margin:0;font-weight:600}
select,button,input[type=file]{font:inherit;color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px}
button{cursor:pointer}
button:hover{border-color:var(--acc)}
main{max-width:820px;margin:0 auto;padding:24px 20px 60px}
#meta{color:var(--dim);font-size:14px;margin-bottom:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px;min-height:220px;display:flex;flex-direction:column;justify-content:center;gap:16px}
.q{font-size:20px;font-weight:600}
.a{border-top:1px dashed var(--line);padding-top:16px;white-space:pre-wrap}
.hidden{display:none}
.row{display:flex;gap:10px;justify-content:space-between;align-items:center;margin-top:16px;flex-wrap:wrap}
.dim{color:var(--dim);font-size:13px}
.tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <h1>Anki Hub</h1>
  <label>Deck <select id="deck"></select></label>
  <span id="progress" class="dim">0 / 0 reviewed</span>
  <div class="tools">
    <button id="exportTSV" type="button">Export TSV</button>
    <label class="dim" for="importTSV">Import TSV</label>
    <input id="importTSV" type="file" accept=".tsv,text/tab-separated-values,text/plain">
  </div>
</header>
<main>
  <div id="meta" class="dim"></div>
  <section class="card">
    <div id="question" class="q"></div>
    <div id="answer" class="a hidden"></div>
  </section>
  <div class="row">
    <button id="prev" type="button">&larr; Prev</button>
    <button id="flip" type="button">Flip</button>
    <button id="next" type="button">Next &rarr;</button>
  </div>
</main>
<script>
var DATA = __DATA__;
var state = {deck: "all", index: 0, reviewed: {}};
function el(id) { return document.getElementById(id); }

function allDecks() {
  var merged = DATA.reduce(function (acc, d) { return acc.concat(d.cards); }, []);
  return [{name: "all", cards: merged}].concat(DATA);
}
function deckCards() {
  var match = allDecks().filter(function (d) { return d.name === state.deck; })[0];
  return match ? match.cards : [];
}
function cardKey(card, i) { return state.deck + "|" + i + "|" + card.q; }

function renderDeckOptions() {
  var sel = el("deck");
  sel.textContent = "";
  allDecks().forEach(function (d) {
    var o = document.createElement("option");
    o.value = d.name;
    o.textContent = d.name + " (" + d.cards.length + " cards)";
    sel.appendChild(o);
  });
  sel.value = state.deck;
}

function render() {
  var cards = deckCards();
  var done = 0;
  cards.forEach(function (c, i) { if (state.reviewed[cardKey(c, i)]) done += 1; });
  el("progress").textContent = done + " / " + cards.length + " reviewed";
  if (!cards.length) {
    el("question").textContent = "(no cards)";
    el("answer").textContent = "";
    el("answer").className = "a hidden";
    el("meta").textContent = "Deck " + state.deck + " has no cards.";
    return;
  }
  if (state.index >= cards.length) state.index = 0;
  if (state.index < 0) state.index = cards.length - 1;
  var card = cards[state.index];
  el("question").textContent = card.q;
  el("answer").textContent = card.a || "(no content)";
  el("answer").className = "a hidden";
  el("meta").textContent = "Card " + (state.index + 1) + " of " + cards.length +
    (card.src ? "  \u00b7  " + card.src : "");
}

function flip() { el("answer").className = "a"; markReviewed(); }
function markReviewed() {
  var cards = deckCards();
  if (cards.length) {
    state.reviewed[cardKey(cards[state.index], state.index)] = true;
    render();
  }
}
function next() {
  var cards = deckCards();
  if (!cards.length) return;
  markReviewed();
  state.index = (state.index + 1) % cards.length;
  render();
}
function prev() {
  var cards = deckCards();
  if (!cards.length) return;
  state.index = (state.index - 1 + cards.length) % cards.length;
  render();
}

function toTSV(cards) {
  var clean = function (s) { return String(s || "").replace(/[\\t\\r\\n]+/g, " "); };
  return cards.map(function (c) { return clean(c.q) + "\\t" + clean(c.a); }).join("\\n") + "\\n";
}
function exportTSV() {
  var blob = new Blob([toTSV(deckCards())], {type: "text/tab-separated-values"});
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url;
  a.download = "anki-" + state.deck + ".tsv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function parseTSV(text) {
  return text.split(/\\r?\\n/)
    .filter(function (l) { return l.trim() !== ""; })
    .map(function (line) {
      var parts = line.split("\\t");
      return {q: (parts[0] || "").trim(), a: (parts[1] || "").trim(), src: "imported"};
    })
    .filter(function (c) { return c.q; });
}
function importTSV(text) {
  var parsed = parseTSV(text);
  if (!parsed.length) return;
  var name = state.deck === "all" ? "imported" : state.deck;
  DATA = DATA.filter(function (d) { return d.name !== name; })
    .concat([{name: name, cards: parsed}]);
  state.deck = name;
  state.index = 0;
  state.reviewed = {};
  renderDeckOptions();
  render();
}

el("deck").addEventListener("change", function (e) {
  state.deck = e.target.value;
  state.index = 0;
  render();
});
el("flip").addEventListener("click", flip);
el("next").addEventListener("click", next);
el("prev").addEventListener("click", prev);
el("exportTSV").addEventListener("click", exportTSV);
el("importTSV").addEventListener("change", function (e) {
  var file = e.target.files && e.target.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function () { importTSV(String(reader.result || "")); };
  reader.readAsText(file);
});
document.addEventListener("keydown", function (e) {
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); }
  else if (e.key === "ArrowRight") next();
  else if (e.key === "ArrowLeft") prev();
});

state.deck = allDecks()[0].name;
renderDeckOptions();
render();
</script>
</body>
</html>
"""


def render_html(decks):
    return PAGE.replace("__DATA__", json.dumps(decks, ensure_ascii=False))


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def run(workspace, dry_run=False, deps=None):
    """Render the Anki hub; return step evidence valid for step.schema.json."""
    workspace = Path(workspace)
    started_at = _now()
    cleaned = workspace / "02_sift" / "cleaned"
    out_path = workspace / "04_render" / "anki.html"
    errors = []

    try:
        decks = collect(cleaned)
    except Exception as exc:  # noqa: BLE001 - serialize as evidence
        decks = []
        errors.append("collect failed: %s" % exc)

    card_count = sum(len(d["cards"]) for d in decks)
    html = render_html(decks)
    size = len(html.encode("utf-8"))

    if not dry_run:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
        except OSError as exc:
            errors.append("write failed: %s" % exc)

    if dry_run:
        status = "skipped"
    elif errors:
        status = "failed"
    else:
        status = "ok"

    return {
        "stage": STAGE,
        "stage_name": STAGE_NAME,
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "inputs": {
            "workspace": str(workspace.resolve()),
            "notes_dir": str(cleaned),
            "dry_run": bool(dry_run),
        },
        "outputs": [] if dry_run else [str(out_path)],
        "evidence": [
            "decks: %d" % len(decks),
            "cards: %d" % card_count,
            "bytes: %d" % size,
            "output: %s" % out_path,
        ],
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage 4b: render offline Anki hub HTML.")
    parser.add_argument("--workspace", default="./workspace")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = run(Path(args.workspace), dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in ("ok", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
