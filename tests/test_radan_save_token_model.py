from __future__ import annotations

import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import ezdxf

from ddc_number_codec import encode_ddc_number_fraction
from radan_save_token_model import build_radan_save_token_model, choose_radan_save_canonical_token


def _write_line_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0, 0), (1, 0, 0))
    doc.saveas(path)


def _sym_text(delta_x_token: str) -> str:
    geometry = f"..{delta_x_token}."
    return f"""<RadanFile extension="ddc"><![CDATA[
G,,1,3,,1,,,1,,{geometry},.,,,
]]></RadanFile>"""


class RadanSaveTokenModelTests(unittest.TestCase):
    def test_builds_model_from_count_matched_after_save_exact_tokens(self) -> None:
        good_token = encode_ddc_number_fraction(Fraction(1))
        before_token = encode_ddc_number_fraction(Fraction("1.000000000000001"))
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for folder in ("dxf", "before", "after", "oracle"):
                (root / folder).mkdir()
            _write_line_dxf(root / "dxf" / "Part A.dxf")
            (root / "before" / "Part A.sym").write_text(_sym_text(before_token), encoding="utf-8")
            (root / "after" / "Part A.sym").write_text(_sym_text(good_token), encoding="utf-8")
            (root / "oracle" / "Part A.sym").write_text(_sym_text(good_token), encoding="utf-8")

            model = build_radan_save_token_model(
                dxf_folder=root / "dxf",
                before_folder=root / "before",
                after_folder=root / "after",
                oracle_folder=root / "oracle",
            )

        self.assertEqual(model["eligible_part_count"], 1)
        self.assertEqual(model["observation_count"], 1)
        observation = model["observations"][0]
        self.assertEqual(observation["before_token"], before_token)
        self.assertEqual(observation["target_token"], good_token)

    def test_choose_token_applies_only_to_fallback_source_and_excludes_same_part(self) -> None:
        good_token = encode_ddc_number_fraction(Fraction(1))
        before_token = encode_ddc_number_fraction(Fraction("1.000000000000001"))
        model = {
            "decoded_tolerance": 1e-12,
            "lookup": {
                "before_token": {
                    (before_token,): [
                        ("Part A", good_token),
                        ("Part B", good_token),
                    ]
                }
            },
        }

        unchanged, unchanged_source = choose_radan_save_canonical_token(
            model=model,
            mode="fallback-token-majority",
            target_part="Part C",
            dxf_type="LINE",
            role="delta_x",
            visible_value_key="1.000000",
            before_token=before_token,
            token_source="same_type_role_fraction",
        )
        changed, changed_source = choose_radan_save_canonical_token(
            model=model,
            mode="fallback-token-majority",
            target_part="Part C",
            dxf_type="LINE",
            role="delta_x",
            visible_value_key="1.000000",
            before_token=before_token,
            token_source="encoded_fraction_fallback:trimmed:0",
        )

        self.assertEqual(unchanged, before_token)
        self.assertEqual(unchanged_source, "")
        self.assertEqual(changed, good_token)
        self.assertIn("radan_save_token:fallback-token-majority", changed_source)

    def test_choose_token_does_not_leak_same_part_observation(self) -> None:
        good_token = encode_ddc_number_fraction(Fraction(1))
        before_token = encode_ddc_number_fraction(Fraction("1.000000000000001"))
        model = {
            "decoded_tolerance": 1e-12,
            "lookup": {"before_token": {(before_token,): [("Part A", good_token)]}},
        }

        token, source = choose_radan_save_canonical_token(
            model=model,
            mode="fallback-token-majority",
            target_part="Part A",
            dxf_type="LINE",
            role="delta_x",
            visible_value_key="1.000000",
            before_token=before_token,
            token_source="encoded_fraction_fallback:trimmed:0",
        )

        self.assertEqual(token, before_token)
        self.assertEqual(source, "")

    def test_shorter_majority_mode_only_accepts_shorter_tokens(self) -> None:
        short_token = encode_ddc_number_fraction(Fraction(1))
        long_token = encode_ddc_number_fraction(Fraction("1.000000000000001"))
        model = {
            "decoded_tolerance": 1e-12,
            "lookup": {"before_token": {(long_token,): [("Part A", short_token)]}},
        }

        token, source = choose_radan_save_canonical_token(
            model=model,
            mode="fallback-shorter-majority",
            target_part="Part B",
            dxf_type="LINE",
            role="delta_x",
            visible_value_key="1.000000",
            before_token=long_token,
            token_source="encoded_fraction_fallback:trimmed:0",
        )
        self.assertEqual(token, short_token)
        self.assertIn("radan_save_token:fallback-shorter-majority", source)

        reject_model = {
            "decoded_tolerance": 1e-12,
            "lookup": {"before_token": {(short_token,): [("Part A", long_token)]}},
        }
        token, source = choose_radan_save_canonical_token(
            model=reject_model,
            mode="fallback-shorter-majority",
            target_part="Part B",
            dxf_type="LINE",
            role="delta_x",
            visible_value_key="1.000000",
            before_token=short_token,
            token_source="encoded_fraction_fallback:trimmed:0",
        )
        self.assertEqual(token, short_token)
        self.assertEqual(source, "")


if __name__ == "__main__":
    unittest.main()
