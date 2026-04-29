from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import analyze_nest_layout_token_deltas as analyzer


def _write_drg(path: Path, rows: list[str]) -> None:
    path.write_text(
        '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
        + "\n".join(rows)
        + "\n]]></RadanFile></RadanCompoundDocument>\n",
        encoding="utf-8",
    )


class AnalyzeNestLayoutTokenDeltasTests(unittest.TestCase):
    def test_analyze_pair_dirs_summarizes_layout_token_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            _write_drg(
                left / "P15 F54410 PAINT PACK.left.drg",
                [
                    "F,:,1,1,,,,,,1,1,1,1,,,1,,m?0.o?0.$/layout/B-10",
                    "I,,1,2,,5,1,1,,n?0.$\\|2",
                    "N,,4,1,,2,$1777499697",
                ],
            )
            _write_drg(
                right / "P15 F54410 PAINT PACK.right.drg",
                [
                    "F,:,1,1,,,,,,1,1,1,1,,,1,,m?1.o?0.$/layout/B-10",
                    "I,,1,2,,5,1,1,,n?1.$\\|2",
                    "N,,4,1,,2,$1777500510",
                ],
            )

            result = analyzer.analyze_pair_dirs(left, right, left_name="raw", right_name="good")

        self.assertEqual(result["paired_drg_count"], 1)
        self.assertEqual(
            result["ddc_changed_by_class"],
            {
                "F layout entity token payload": 1,
                "I layout annotation token payload": 1,
                "N numeric cache/timestamp": 1,
            },
        )
        self.assertEqual(result["layout_changed_rows"], 2)
        self.assertEqual(result["layout_token_summary"]["token_mismatch_count"], 2)
        self.assertEqual(result["layout_token_summary"]["decoded_bucket_counts"], {"far": 2})

    def test_assert_sym_lab_output_rejects_non_lab_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                analyzer._assert_sym_lab_output(Path(tmpdir) / "out.json")


if __name__ == "__main__":
    unittest.main()
