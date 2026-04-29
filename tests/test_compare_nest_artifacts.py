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

import compare_nest_artifacts as compare


def _write_rpd(path: Path, label: str, sym_folder: str) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanProject xmlns="http://www.radan.com/ns/project">\n'
        '  <Nests>\n'
        f'    <Nest><FileName>P15 F54410 PAINT PACK.{label}.drg</FileName><ID>15</ID>\n'
        '      <SheetUsed><Used>1</Used><Material>Aluminum 5052</Material><Thickness>0.25</Thickness>'
        '<SheetX>120</SheetX><SheetY>60</SheetY></SheetUsed>\n'
        '      <PartsMade>\n'
        f'        <PartMade><File>C:\\lab\\{sym_folder}\\B-10.sym</File><Made>2</Made></PartMade>\n'
        f'        <PartMade><File>C:\\lab\\{sym_folder}\\B-184.sym</File><Made>4</Made></PartMade>\n'
        '      </PartsMade>\n'
        '    </Nest>\n'
        '  </Nests>\n'
        '</RadanProject>\n',
        encoding="utf-8",
    )


def _write_drg(path: Path, label: str, sym_folder: str) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanCompoundDocument>\n'
        f'  <Attr name="Drawing" value="P15 F54410 PAINT PACK.{label}"/>\n'
        '  <Attr name="Nest time" value="2026-04-29T18:00:00-04:00"/>\n'
        '  <RadanFile extension="ddc"><![CDATA[\n'
        f'U,,$C:\\lab\\{sym_folder}\\B-10.sym\n'
        f'U,,$C:\\lab\\{sym_folder}\\B-184.sym\n'
        '  ]]></RadanFile>\n'
        '  <Info num="4" name="Contained Symbols"><Symbol name="B-10" count="2"/><Symbol name="B-184" count="4"/></Info>\n'
        '</RadanCompoundDocument>\n',
        encoding="utf-8",
    )


class CompareNestArtifactsTests(unittest.TestCase):
    def test_normalize_drg_text_removes_labels_paths_and_timestamps(self) -> None:
        left = (
            "P15 F54410 PAINT PACK.raw\n"
            "2026-04-29T18:00:00-04:00\n"
            "U,,$C:\\lab\\before\\B-10.sym\n"
        )
        right = (
            "P15 F54410 PAINT PACK.saved\n"
            "2026-04-29T18:05:00-04:00\n"
            "U,,$\\\\SVRDC\\Laser\\BATTLESHIELD\\F-LARGE FLEET\\F54410\\PAINT PACK\\B-10.sym\n"
        )

        self.assertEqual(compare.normalize_drg_text(left), compare.normalize_drg_text(right))

    def test_compare_gate_dirs_matches_semantic_outputs_after_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            _write_rpd(left / "left.rpd", "raw", "before")
            _write_rpd(right / "right.rpd", "saved", "after_radan_save")
            _write_drg(left / "P15 F54410 PAINT PACK.raw.drg", "raw", "before")
            _write_drg(right / "P15 F54410 PAINT PACK.saved.drg", "saved", "after_radan_save")

            result = compare.compare_gate_dirs(left, right, left_name="raw", right_name="saved")

        self.assertTrue(result["rpd_used_nests_match"])
        self.assertEqual(result["drg_count_match"], True)
        self.assertEqual(result["drg_full_hash_matches"], 0)
        self.assertEqual(result["drg_normalized_hash_matches"], 1)
        self.assertEqual(result["drg_contained_symbols_matches"], 1)
        self.assertEqual(result["ddc_changed_lines"], 0)

    def test_compare_ddc_lines_counts_prefix_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            left = root / "left.drg"
            right = root / "right.drg"
            left.write_text(
                '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
                "G,,same\n"
                "H,,left\n"
                "I,,left-note\n"
                "]]></RadanFile></RadanCompoundDocument>\n",
                encoding="utf-8",
            )
            right.write_text(
                '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
                "G,,same\n"
                "H,,right\n"
                "N,,right-note\n"
                "]]></RadanFile></RadanCompoundDocument>\n",
                encoding="utf-8",
            )

            result = compare.compare_ddc_lines(left, right)

        self.assertEqual(result["same_lines"], 1)
        self.assertEqual(result["changed_lines"], 2)
        self.assertEqual(result["changed_by_prefix"], {"H->H": 1, "I->N": 1})


if __name__ == "__main__":
    unittest.main()
