from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import run_thumbnail_parity_gate as gate


class ThumbnailParityGateTests(unittest.TestCase):
    def test_compare_images_reports_exact_match_and_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left.png"
            right = root / "right.png"
            changed = root / "changed.png"
            Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(left)
            Image.new("RGBA", (2, 2), (0, 0, 0, 0)).save(right)
            image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
            image.putpixel((1, 1), (255, 0, 0, 255))
            image.save(changed)

            exact = gate.compare_images(left, right)
            diff = gate.compare_images(left, changed)

        self.assertTrue(exact["ok"])
        self.assertEqual(exact["diff_pixels"], 0)
        self.assertFalse(diff["ok"])
        self.assertEqual(diff["diff_pixels"], 1)
        self.assertEqual(diff["diff_bbox"], [1, 1, 2, 2])

    def test_run_gate_records_missing_symbol_without_radan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            candidate = root / "candidate"
            oracle = root / "oracle"
            candidate.mkdir()
            oracle.mkdir()

            with mock.patch.object(gate, "assert_lab_output_path"):
                payload = gate.run_gate(
                    candidate_symbol_folder=candidate,
                    oracle_symbol_folder=oracle,
                    out_dir=lab_root / "thumbs",
                    parts=["B-10"],
                )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["part_count"], 1)
        self.assertIn("Missing candidate symbol", payload["comparisons"][0]["error"])


if __name__ == "__main__":
    unittest.main()
