from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import generate_toxic_token_spelling_variants as variants
from ddc_corpus import read_ddc_records


def _sym(rows: list[str]) -> str:
    return (
        '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
        + "\n".join(rows)
        + "\n]]></RadanFile></RadanCompoundDocument>\n"
    )


class GenerateToxicTokenSpellingVariantsTests(unittest.TestCase):
    def test_shift_last_continuation_digit_can_append_zero(self) -> None:
        self.assertEqual(
            variants.shift_last_continuation_digit("m?;djH4hNN", shift=2, append_zeros=1),
            "m?;djH4hNP0",
        )
        self.assertEqual(
            variants.shift_last_continuation_digit("m?[djH4hNN", shift=-2, append_zeros=1),
            "m?[djH4hNL0",
        )

    def test_shift_rejects_empty_short_and_out_of_range_tokens(self) -> None:
        with self.assertRaises(ValueError):
            variants.shift_last_continuation_digit("", shift=1)
        with self.assertRaises(ValueError):
            variants.shift_last_continuation_digit("o?0", shift=1)
        with self.assertRaises(ValueError):
            variants.shift_last_continuation_digit("m?;", shift=100)

    def test_replace_geometry_token_records_decoded_delta(self) -> None:
        text = _sym(
            [
                "G,,1,A,,,,,1,,4@1R.4@1j5RcmS`a..m?;djH4hNN.............,.,,,",
                "H,,1,B,,,,,1,,a.b.c,,,,",
            ]
        )
        patch = variants.TokenShiftPatch(
            "F54410-B-37",
            row_index=1,
            slot=3,
            shift=2,
            append_zeros=1,
            note="test",
        )

        patched, result = variants._replace_geometry_token(text, patch)

        rows = read_ddc_records_from_text(patched)
        self.assertEqual(rows[0]["tokens"][3], "m?;djH4hNP0")
        self.assertEqual(result["old_token"], "m?;djH4hNN")
        self.assertEqual(result["new_token"], "m?;djH4hNP0")
        self.assertGreater(result["delta"], 0)

    def test_parse_patch_spec(self) -> None:
        name, patch = variants.parse_patch_spec("custom:F54410-B-37:12:3:2:1:delta rule")
        self.assertEqual(name, "custom")
        self.assertEqual(patch.part, "F54410-B-37")
        self.assertEqual(patch.row_index, 12)
        self.assertEqual(patch.slot, 3)
        self.assertEqual(patch.shift, 2)
        self.assertEqual(patch.append_zeros, 1)
        self.assertEqual(patch.note, "delta rule")


def read_ddc_records_from_text(text: str) -> list[dict[str, object]]:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "P.sym"
        path.write_text(text, encoding="utf-8")
        return read_ddc_records(path)


if __name__ == "__main__":
    unittest.main()
