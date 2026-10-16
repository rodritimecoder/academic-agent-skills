import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import format_notes
import srs_review


SAMPLE_CORNELL_DATA = {
    "title": "Quantum Computing Fundamentals",
    "source": "physics_lecture_01.md",
    "sections": [
        {
            "heading": "Qubits and Superposition",
            "entries": [
                {
                    "cue": "What is a qubit?",
                    "notes": "The fundamental unit of quantum information, capable of existing in a linear superposition of $|0\\rangle$ and $|1\\rangle$."
                },
                {
                    "cue": "Explain the Bloch Sphere",
                    "notes": "A geometric representation of the pure state space of a two-level quantum mechanical system (qubit)."
                }
            ],
            "summary": "Qubits generalize classical bits by admitting continuous complex superposition states geometrically mapped on the Bloch sphere."
        },
        {
            "heading": "Quantum Gates",
            "entries": [
                {
                    "cue": "What does a Hadamard (H) gate do?",
                    "notes": "Maps computational basis states $|0\\rangle$ and $|1\\rangle$ to equal superposition states $|+\\rangle$ and $|-\\rangle$."
                }
            ],
            "summary": "Quantum gates are unitary transformations that manipulate qubit state vectors on the Bloch sphere."
        }
    ]
}


class TestFormatNotes(unittest.TestCase):
    def test_validate_schema_valid(self):
        errors = format_notes.validate_schema(SAMPLE_CORNELL_DATA)
        self.assertEqual(errors, [])

    def test_validate_schema_invalid(self):
        bad_data = {"sections": [{"heading": "No entries"}]}
        errors = format_notes.validate_schema(bad_data)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("title" in e for e in errors))
        self.assertTrue(any("entries" in e for e in errors))

    def test_render_table(self):
        rows = [
            {"section": "Intro", "cues": 2, "summary": "Short summary"},
            {"section": "Advanced", "cues": 5, "summary": "Deeper summary"},
        ]
        table = format_notes.render_table(rows, ["section", "cues", "summary"])
        self.assertIn("| Section  | Cues | Summary        |", table)
        self.assertIn("| Intro    | 2    | Short summary  |", table)
        self.assertIn("| Advanced | 5    | Deeper summary |", table)

    def test_outline_mode_table_and_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "notes_cornell.json"
            json_file.write_text(json.dumps(SAMPLE_CORNELL_DATA), encoding="utf-8")

            # Table outline
            buf = io.StringIO()
            with patch("sys.stdout", buf), patch("sys.argv", ["format_notes.py", str(json_file), "--outline"]):
                format_notes.main()
            out_table = buf.getvalue()
            self.assertIn("### Cornell Notes Outline: Quantum Computing Fundamentals", out_table)
            self.assertIn("| Qubits and Superposition | 2    |", out_table)
            self.assertIn("| Quantum Gates            | 1    |", out_table)

            # JSON outline with limit
            buf = io.StringIO()
            with patch("sys.stdout", buf), patch("sys.argv", ["format_notes.py", str(json_file), "--outline", "--json", "-n", "1"]):
                format_notes.main()
            out_json = json.loads(buf.getvalue().strip())
            self.assertEqual(len(out_json), 1)
            self.assertEqual(out_json[0]["section"], "Qubits and Superposition")
            self.assertEqual(out_json[0]["cues"], 2)

    def test_stats_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "notes_cornell.json"
            json_file.write_text(json.dumps(SAMPLE_CORNELL_DATA), encoding="utf-8")

            buf = io.StringIO()
            with patch("sys.stdout", buf), patch("sys.argv", ["format_notes.py", str(json_file), "--stats", "--json"]):
                format_notes.main()
            stats = json.loads(buf.getvalue().strip())
            self.assertEqual(stats["sections"], 2)
            self.assertEqual(stats["cues"], 3)
            self.assertEqual(stats["summaries"], 2)

    def test_render_html_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "sample_cornell.json"
            json_file.write_text(json.dumps(SAMPLE_CORNELL_DATA), encoding="utf-8")

            buf = io.StringIO()
            with patch("sys.stdout", buf), patch("sys.argv", ["format_notes.py", str(json_file), "--table", "--anki"]):
                format_notes.main()
            receipt = buf.getvalue()
            self.assertIn("### Cornell Notes Receipt", receipt)
            self.assertIn("| Cue-Note Pairs | 3", receipt)
            self.assertIn("anki.tsv (3 cards)", receipt)

            out_html = Path(tmpdir) / "sample_cornell.html"
            out_anki = Path(tmpdir) / "sample_cornell_anki.tsv"
            self.assertTrue(out_html.exists())
            self.assertTrue(out_anki.exists())


class TestSrsReview(unittest.TestCase):
    def test_card_id_deterministic(self):
        cid1 = srs_review.card_id("Heading A", "What is X?")
        cid2 = srs_review.card_id("Heading A", "What is X?")
        cid3 = srs_review.card_id("Heading B", "What is X?")
        self.assertEqual(cid1, cid2)
        self.assertNotEqual(cid1, cid3)

    def test_calculate_sm2(self):
        # Again/Fail resets reps and interval to 1
        reps, interval, ease, due = srs_review.calculate_sm2(quality=0, reps=3, interval_days=10, ease_factor=2.5)
        self.assertEqual(reps, 0)
        self.assertEqual(interval, 1)

        # First pass good
        reps, interval, ease, due = srs_review.calculate_sm2(quality=3, reps=0, interval_days=1, ease_factor=2.5)
        self.assertEqual(reps, 1)
        self.assertEqual(interval, 1)

        # Second pass good
        reps, interval, ease, due = srs_review.calculate_sm2(quality=3, reps=1, interval_days=1, ease_factor=2.5)
        self.assertEqual(reps, 2)
        self.assertEqual(interval, 3)

    def test_cmd_status_all_table_and_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            json_file = tmppath / "physics_cornell.json"
            json_file.write_text(json.dumps(SAMPLE_CORNELL_DATA), encoding="utf-8")

            # Table mode
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                srs_review.cmd_status_all(tmppath, as_table=True)
            table_out = buf.getvalue()
            self.assertIn("### Spaced Repetition (SRS) Status", table_out)
            self.assertIn("physics_cornell.json", table_out)
            self.assertIn("Quantum Computing Fundamentals", table_out)

            # JSON mode with projection
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                srs_review.cmd_status_all(tmppath, as_json=True, project_keys=["title", "cards", "new"])
            json_out = json.loads(buf.getvalue().strip())
            self.assertEqual(len(json_out), 1)
            self.assertEqual(json_out[0], {
                "title": "Quantum Computing Fundamentals",
                "cards": 3,
                "new": 3
            })


if __name__ == "__main__":
    unittest.main()
