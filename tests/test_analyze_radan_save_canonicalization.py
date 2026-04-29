from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyze_radan_save_canonicalization import _classify_part, _multiset_stats
from ddc_number_codec import encode_ddc_number_fraction


def _sym_text(rows: list[str]) -> str:
    return "<RadanFile extension=\"ddc\"><![CDATA[\n" + "\n".join(rows) + "\n]]></RadanFile>"


class AnalyzeRadanSaveCanonicalizationTests(unittest.TestCase):
    def _metrics(
        self,
        *,
        count_match: bool = True,
        type_sequence_match: bool = True,
        max_decoded_abs_diff: float = 0.0,
        exact_geometry_data_matches: int = 0,
        paired_record_count: int = 1,
        token_match_ratio: float = 0.5,
        geometry_multiset_match_without_pen: bool = False,
    ) -> dict[str, object]:
        return {
            "count_match": count_match,
            "type_sequence_match": type_sequence_match,
            "max_decoded_abs_diff": max_decoded_abs_diff,
            "exact_geometry_data_matches": exact_geometry_data_matches,
            "paired_record_count": paired_record_count,
            "token_match_ratio": token_match_ratio,
            "geometry_multiset_match_without_pen": geometry_multiset_match_without_pen,
        }

    def test_classifies_row_count_change_as_destructive_repair(self) -> None:
        result = _classify_part(
            before=self._metrics(token_match_ratio=0.9),
            after=self._metrics(count_match=False, token_match_ratio=0.95),
            decoded_tolerance=1e-12,
        )

        self.assertEqual(result, "destructive_radan_repair_row_count_changed")

    def test_classifies_exact_after_save_before_improvement_bucket(self) -> None:
        result = _classify_part(
            before=self._metrics(token_match_ratio=0.9),
            after=self._metrics(
                token_match_ratio=1.0,
                exact_geometry_data_matches=4,
                paired_record_count=4,
            ),
            decoded_tolerance=1e-12,
        )

        self.assertEqual(result, "exact_after_save")

    def test_classifies_decoded_close_token_improvement(self) -> None:
        result = _classify_part(
            before=self._metrics(token_match_ratio=0.82),
            after=self._metrics(token_match_ratio=0.95, exact_geometry_data_matches=2, paired_record_count=4),
            decoded_tolerance=1e-12,
        )

        self.assertEqual(result, "canonicalized_closer")

    def test_classifies_row_order_change_when_multiset_matches_but_pairing_differs(self) -> None:
        result = _classify_part(
            before=self._metrics(token_match_ratio=0.9),
            after=self._metrics(
                max_decoded_abs_diff=10.0,
                token_match_ratio=0.7,
                geometry_multiset_match_without_pen=True,
            ),
            decoded_tolerance=1e-12,
        )

        self.assertEqual(result, "row_order_changed")

    def test_multiset_stats_can_ignore_pen_differences(self) -> None:
        token = encode_ddc_number_fraction(1)
        geometry = f"{token}..."
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            good = root / "good.sym"
            compare = root / "compare.sym"
            good.write_text(_sym_text([f"G,,1,3,,1,,,1,,{geometry},.,,,"]), encoding="utf-8")
            compare.write_text(_sym_text([f"G,,1,3,,1,,,2,,{geometry},.,,,"]), encoding="utf-8")

            stats = _multiset_stats(good, compare)

        self.assertTrue(stats["geometry_multiset_match_without_pen"])
        self.assertFalse(stats["geometry_multiset_match_with_pen"])
        self.assertEqual(stats["geometry_multiset_common_without_pen"], 1)
        self.assertEqual(stats["geometry_multiset_common_with_pen"], 0)


if __name__ == "__main__":
    unittest.main()
