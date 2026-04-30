from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import build_sym_token_patch_variant as patcher
from ddc_corpus import read_ddc_records


def _sym(rows: list[str]) -> str:
    return (
        '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
        + "\n".join(rows)
        + "\n]]></RadanFile></RadanCompoundDocument>\n"
    )


class BuildSymTokenPatchVariantTests(unittest.TestCase):
    def test_parse_patch_spec_uses_one_based_rows_and_zero_based_slots(self) -> None:
        self.assertEqual(
            patcher.parse_patch_spec("B-185:11:2"),
            {"part": "B-185", "row_index": 11, "slot": 2, "source": "spec"},
        )

        with self.assertRaises(ValueError):
            patcher.parse_patch_spec("B-185:0:2")

    def test_parse_field_patch_spec_uses_one_based_rows_and_zero_based_fields(self) -> None:
        self.assertEqual(
            patcher.parse_field_patch_spec("B-185:13:3:@"),
            {
                "part": "B-185",
                "row_index": 13,
                "field_index": 3,
                "field_value": "@",
                "source": "field-spec",
            },
        )

        with self.assertRaises(ValueError):
            patcher.parse_field_patch_spec("B-185:13:-1:@")

    def test_load_patch_csv_filters_matches_roles_and_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "patches.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["part", "row_index", "slot", "role", "token_match"])
                writer.writeheader()
                writer.writerow({"part": "B-185", "row_index": "11", "slot": "2", "role": "delta_x", "token_match": "False"})
                writer.writerow({"part": "B-185", "row_index": "13", "slot": "2", "role": "delta_x", "token_match": "True"})
                writer.writerow({"part": "B-186", "row_index": "1", "slot": "1", "role": "start_y", "token_match": "False"})

            patches = patcher.load_patch_csv(path, roles=["delta_x"], parts=["B-185"])

        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["part"], "B-185")
        self.assertEqual(patches[0]["row_index"], 11)

    def test_build_token_patch_variant_copies_source_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base = root / "base"
            source = root / "source"
            out = root / "_sym_lab" / "variant"
            base.mkdir()
            source.mkdir()
            (base / "P1.sym").write_text(
                _sym(["G,,,,,,,,,,a.b.c", "H,,,,,,,,,,d.e.f"]),
                encoding="utf-8",
            )
            (source / "P1.sym").write_text(
                _sym(["G,,,,,,,,,,x.y.z", "H,,,,,,,,,,u.v.w"]),
                encoding="utf-8",
            )

            manifest = patcher.build_token_patch_variant(
                base_folder=base,
                source_folder=source,
                out_dir=out,
                patches=[{"part": "P1", "row_index": 2, "slot": 1, "source": "test"}],
                lab_root=root / "_sym_lab",
            )

            rows = read_ddc_records(out / "P1.sym")
            patched_text = (out / "P1.sym").read_text(encoding="utf-8")

        self.assertEqual(manifest["copied_symbol_count"], 1)
        self.assertEqual(manifest["changed_patch_count"], 1)
        self.assertEqual(rows[0]["tokens"], ["a", "b", "c"])
        self.assertEqual(rows[1]["tokens"], ["d", "v", "f"])
        self.assertIn("d.v.f\n]]>", patched_text)

    def test_build_token_patch_variant_can_patch_ddc_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            base = root / "base"
            source = root / "source"
            out = root / "_sym_lab" / "field_variant"
            base.mkdir()
            source.mkdir()
            (base / "P1.sym").write_text(
                _sym(["G,,1,A,,,,,,,a.b.c", "H,,1,B,,,,,,,d.e.f"]),
                encoding="utf-8",
            )
            (source / "P1.sym").write_text(_sym(["G,,1,A,,,,,,,x.y.z"]), encoding="utf-8")

            manifest = patcher.build_token_patch_variant(
                base_folder=base,
                source_folder=source,
                out_dir=out,
                patches=[],
                field_patches=[
                    {"part": "P1", "row_index": 2, "field_index": 3, "field_value": "Z", "source": "test"}
                ],
                lab_root=root / "_sym_lab",
            )

            rows = read_ddc_records(out / "P1.sym")
            patched_text = (out / "P1.sym").read_text(encoding="utf-8")

        self.assertEqual(manifest["field_patch_count"], 1)
        self.assertEqual(manifest["changed_field_patch_count"], 1)
        self.assertEqual(rows[1]["identifier"], "Z")
        self.assertIn("H,,1,Z,,,,,,,d.e.f\n]]>", patched_text)

    def test_default_lab_guard_rejects_non_lab_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                patcher.assert_lab_output_path(Path(tmpdir) / "variant")


if __name__ == "__main__":
    unittest.main()
