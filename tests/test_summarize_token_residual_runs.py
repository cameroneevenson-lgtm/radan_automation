from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import summarize_token_residual_runs as summarize


class SummarizeTokenResidualRunsTests(unittest.TestCase):
    def test_summarize_runs_extracts_compact_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "run.json"
            path.write_text(
                json.dumps(
                    {
                        "part_count": 2,
                        "summary": {
                            "slot_count": 10,
                            "exact_token_count": 8,
                            "exact_token_rate": 0.8,
                            "mismatch_count": 2,
                            "close_mismatch_count": 2,
                            "far_mismatch_count": 0,
                            "same_prefix_except_last_char_count": 1,
                            "top_roles_by_mismatch": [{"key": "LINE:start_x", "count": 2}],
                            "top_mantissa_delta_units": [{"key": "1", "count": 2}],
                            "top_last_char_delta": [{"key": "1", "count": 1}],
                        },
                    }
                ),
                encoding="utf-8",
            )

            payload = summarize.summarize_runs([("raw", path)])

        self.assertEqual(payload["runs"][0]["label"], "raw")
        self.assertEqual(payload["runs"][0]["part_count"], 2)
        self.assertEqual(payload["runs"][0]["mismatch_count"], 2)
        self.assertEqual(payload["runs"][0]["top_roles_by_mismatch"][0]["key"], "LINE:start_x")

    def test_markdown_contains_run_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "summary.md"
            summarize.write_markdown(
                {
                    "runs": [
                        {
                            "label": "raw",
                            "part_count": 1,
                            "slot_count": 4,
                            "exact_token_count": 3,
                            "exact_token_rate": 0.75,
                            "mismatch_count": 1,
                            "close_mismatch_count": 1,
                            "far_mismatch_count": 0,
                            "same_prefix_except_last_char_count": 1,
                            "top_roles_by_mismatch": [],
                            "top_mantissa_delta_units": [],
                        }
                    ]
                },
                out,
            )

            text = out.read_text(encoding="utf-8")

        self.assertIn("Token Residual Accepted-Subset Summary", text)
        self.assertIn("`raw`", text)


if __name__ == "__main__":
    unittest.main()
