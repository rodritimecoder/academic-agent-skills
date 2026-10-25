#!/usr/bin/env python3
"""Tests for stage 4b render_anki.py (stdlib unittest only)."""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "render_anki.py"
SCHEMA_PATH = ROOT / "contracts" / "step.schema.json"


def load_module():
    spec = importlib.util.spec_from_file_location("render_anki", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NOTE_ONE = """# Week 1 - Foundations

Reliability means the system keeps working under failure.

## Redundancy

Duplicated components remove single points of failure.

- replicated state
- health checks

## Failure modes

Crash-stop and byzantine are the two broad families.
"""

NOTE_TWO = """# Week 2 - Consensus

Agreement among replicas is the core problem.

## Quorum

Any two majorities intersect in at least one node.

## Leader election

Raft elects a leader with randomized timeouts.
"""


class RenderAnkiTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.cleaned = self.workspace / "02_sift" / "cleaned"
        self.cleaned.mkdir(parents=True)
        (self.cleaned / "note_one.md").write_text(NOTE_ONE, encoding="utf-8")
        (self.cleaned / "note_two.md").write_text(NOTE_TWO, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    # -- extraction ------------------------------------------------------
    def test_one_card_per_heading(self):
        cards = self.module.extract_cards(NOTE_ONE)
        self.assertEqual(
            [c["q"] for c in cards],
            ["Week 1 - Foundations", "Redundancy", "Failure modes"],
        )
        self.assertEqual(
            cards[0]["a"],
            "Reliability means the system keeps working under failure.",
        )
        # first paragraph only, list items after a blank line are excluded
        self.assertEqual(
            cards[1]["a"],
            "Duplicated components remove single points of failure.",
        )
        self.assertEqual(
            cards[2]["a"],
            "Crash-stop and byzantine are the two broad families.",
        )

    def test_note_without_headings_yields_no_cards(self):
        self.assertEqual(self.module.extract_cards("just a paragraph\n"), [])

    def test_run_collects_cards_from_two_notes(self):
        result = self.module.run(self.workspace)
        html = (self.workspace / "04_render" / "anki.html").read_text(encoding="utf-8")
        self.assertIn("Week 1 - Foundations", html)
        self.assertIn("Week 2 - Consensus", html)
        self.assertIn("Quorum", html)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(
            any(ev == "cards: 6" for ev in result["evidence"]),
            result["evidence"],
        )
        self.assertTrue(
            any(ev.startswith("bytes: ") for ev in result["evidence"]),
            result["evidence"],
        )

    # -- html contract ---------------------------------------------------
    def test_tsv_handlers_present(self):
        self.module.run(self.workspace)
        html = (self.workspace / "04_render" / "anki.html").read_text(encoding="utf-8")
        self.assertIn("function exportTSV", html)
        self.assertIn("function importTSV", html)
        self.assertIn("text/tab-separated-values", html)
        self.assertIn('id="importTSV"', html)

    def test_no_external_script_src(self):
        self.module.run(self.workspace)
        html = (self.workspace / "04_render" / "anki.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"<script[^>]*\bsrc\s*=", html, re.I), [])
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_review_and_progress_hooks_present(self):
        self.module.run(self.workspace)
        html = (self.workspace / "04_render" / "anki.html").read_text(encoding="utf-8")
        for token in ('id="flip"', 'id="next"', 'id="prev"', 'id="progress"', "function flip"):
            self.assertIn(token, html)
        self.assertRegex(html, r'id="progress"[^>]*>0 / 0 reviewed<')

    def test_single_output_file(self):
        self.module.run(self.workspace)
        rendered = sorted(p.name for p in (self.workspace / "04_render").iterdir())
        self.assertEqual(rendered, ["anki.html"])

    def test_dry_run_writes_nothing(self):
        result = self.module.run(self.workspace, dry_run=True)
        self.assertFalse((self.workspace / "04_render" / "anki.html").exists())
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["outputs"], [])

    # -- step evidence contract ------------------------------------------
    def test_step_keys_exact_and_schema_valid(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        result = self.module.run(self.workspace)
        self.assertEqual(sorted(result), sorted(schema["required"]))
        self.assertEqual(result["stage"], 4)
        self.assertEqual(result["stage_name"], "render")
        self.assertIn(result["status"], schema["properties"]["status"]["enum"])
        self.assertIsInstance(result["inputs"], dict)
        self.assertIsInstance(result["outputs"], list)
        self.assertIsInstance(result["evidence"], list)
        self.assertIsInstance(result["errors"], list)
        self.assertTrue(1 <= result["stage"] <= 5)
        for key in schema["required"]:
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
