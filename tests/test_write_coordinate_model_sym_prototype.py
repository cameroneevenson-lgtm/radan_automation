from __future__ import annotations

import unittest
from fractions import Fraction

from ddc_number_codec import encode_ddc_number_fraction
from write_coordinate_model_sym_prototype import (
    PartPair,
    _compare_tokens,
    _coordinate_point_observations_for_pair,
    _build_context_coordinate_lookup,
    _build_same_part_coordinate_lookup,
    _replace_template_geometry,
    choose_token_for_fraction,
    predict_geometry_tokens,
)


class WriteCoordinateModelSymPrototypeTests(unittest.TestCase):
    def test_choose_token_excludes_same_part_by_default(self) -> None:
        token_a = encode_ddc_number_fraction(Fraction(1, 4), min_continuation_digits=2)
        token_b = encode_ddc_number_fraction(Fraction(1, 4), min_continuation_digits=4)

        token, source = choose_token_for_fraction(
            target_part="P1",
            dxf_row={"type": "LINE"},
            slot=0,
            fraction=Fraction(1, 4),
            token_observations=[
                {
                    "part": "P1",
                    "dxf_type": "LINE",
                    "role": "start_x",
                    "slot": 0,
                    "token": token_a,
                    "fraction": Fraction(1, 4),
                },
                {
                    "part": "P2",
                    "dxf_type": "LINE",
                    "role": "start_x",
                    "slot": 0,
                    "token": token_b,
                    "fraction": Fraction(1, 4),
                },
            ],
        )

        self.assertEqual(token, token_b)
        self.assertEqual(source, "same_type_role_fraction")

    def test_choose_token_can_allow_same_part_oracle_spelling(self) -> None:
        token_a = encode_ddc_number_fraction(Fraction(1, 4), min_continuation_digits=2)
        token_b = encode_ddc_number_fraction(Fraction(1, 4), min_continuation_digits=4)

        token, _source = choose_token_for_fraction(
            target_part="P1",
            dxf_row={"type": "LINE"},
            slot=0,
            fraction=Fraction(1, 4),
            token_observations=[
                {
                    "part": "P1",
                    "dxf_type": "LINE",
                    "role": "start_x",
                    "slot": 0,
                    "token": token_a,
                    "fraction": Fraction(1, 4),
                },
                {
                    "part": "P2",
                    "dxf_type": "LINE",
                    "role": "start_x",
                    "slot": 0,
                    "token": token_b,
                    "fraction": Fraction(1, 4),
                },
            ],
            allow_same_part_token_spelling=True,
        )

        self.assertEqual(token, token_a)

    def test_choose_token_can_predict_fallback_continuation_by_type_role(self) -> None:
        token, source = choose_token_for_fraction(
            target_part="P1",
            dxf_row={"type": "LINE"},
            slot=0,
            fraction=Fraction(1, 8),
            token_observations=[],
            token_lookup={"same_type_role_fraction": {}, "same_role_fraction": {}, "same_fraction": {}},
            min_continuation_lookup={
                "type_role": {("LINE", "start_x"): [("P2", 4), ("P3", 4), ("P4", 0)]},
                "role": {},
            },
            fallback_continuation="type-role",
        )

        self.assertEqual(token, encode_ddc_number_fraction(Fraction(1, 8), min_continuation_digits=4))
        self.assertEqual(source, "encoded_fraction_fallback:type-role:4")

    def test_predict_geometry_tokens_uses_coordinate_lookup_for_line_delta(self) -> None:
        model = {
            "coordinate_lookup": {
                ("x", "1.000000"): {"P1": Fraction(1, 1)},
                ("x", "4.000000"): {"P1": Fraction(4, 1)},
                ("y", "2.000000"): {"P1": Fraction(2, 1)},
                ("y", "1.000000"): {"P1": Fraction(1, 1)},
            },
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "token_observations": [],
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row={
                "type": "LINE",
                "normalized_start": [1.0, 2.0],
                "normalized_end": [4.0, 1.0],
            },
            template_ddc_row={"tokens": ["", "", "", ""]},
            model=model,
        )

        self.assertEqual(tokens[0], encode_ddc_number_fraction(Fraction(1, 1)))
        self.assertEqual(tokens[2], encode_ddc_number_fraction(Fraction(3, 1)))
        self.assertEqual(slot_reports[2]["coordinate_covered"], True)

    def test_context_resolver_can_use_same_part_exact_row_for_ambiguous_visible_values(self) -> None:
        token_one = encode_ddc_number_fraction(Fraction(1, 1))
        token_one_hidden = encode_ddc_number_fraction(Fraction(1000000000001, 1000000000000))
        pair = PartPair(
            part="P1",
            dxf_path=None,  # type: ignore[arg-type]
            sym_path=None,  # type: ignore[arg-type]
            dxf_rows=[
                {
                    "type": "LINE",
                    "normalized_start": [1.0, 0.0],
                    "normalized_end": [2.0, 0.0],
                },
                {
                    "type": "LINE",
                    "normalized_start": [1.0, 1.0],
                    "normalized_end": [2.0, 1.0],
                },
            ],
            ddc_rows=[
                {"tokens": [token_one, "", token_one, ""]},
                {"tokens": [token_one_hidden, encode_ddc_number_fraction(Fraction(1, 1)), token_one, ""]},
            ],
        )
        observations = _coordinate_point_observations_for_pair(pair)
        model = {
            "coordinate_lookup": {},
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "coordinate_point_observations": observations,
            "context_coordinate_lookup": _build_context_coordinate_lookup(observations),
            "same_part_coordinate_lookup": _build_same_part_coordinate_lookup(observations),
            "token_observations": [],
            "token_lookup": {},
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row=pair.dxf_rows[1],
            dxf_rows=pair.dxf_rows,
            row_index=1,
            template_ddc_row={"tokens": ["", "", "", ""]},
            model=model,
            coordinate_resolver="context",
            allow_same_part_coordinate_fallback=True,
        )

        self.assertEqual(tokens[0], token_one_hidden)
        self.assertEqual(slot_reports[0]["coordinate_source"], "same_part_exact_row")

    def test_context_resolver_excludes_same_part_without_oracle_flag(self) -> None:
        pair = PartPair(
            part="P2",
            dxf_path=None,  # type: ignore[arg-type]
            sym_path=None,  # type: ignore[arg-type]
            dxf_rows=[
                {
                    "type": "LINE",
                    "normalized_start": [1.0, 0.0],
                    "normalized_end": [2.0, 0.0],
                }
            ],
            ddc_rows=[
                {
                    "tokens": [
                        encode_ddc_number_fraction(Fraction(101, 100)),
                        "",
                        encode_ddc_number_fraction(Fraction(1, 1)),
                        "",
                    ]
                }
            ],
        )
        observations = _coordinate_point_observations_for_pair(pair)
        model = {
            "coordinate_lookup": {},
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "coordinate_point_observations": observations,
            "context_coordinate_lookup": _build_context_coordinate_lookup(observations),
            "same_part_coordinate_lookup": _build_same_part_coordinate_lookup(observations),
            "token_observations": [],
            "token_lookup": {},
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row=pair.dxf_rows[0],
            dxf_rows=pair.dxf_rows,
            row_index=0,
            template_ddc_row={"tokens": ["", "", "", ""]},
            model=model,
            coordinate_resolver="context",
        )

        self.assertEqual(tokens[0], encode_ddc_number_fraction(Fraction(101, 100)))
        self.assertEqual(slot_reports[0]["coordinate_source"], "entity_role_point_value")

    def test_prefer_literal_geometry_keeps_dyadic_line_values_exact(self) -> None:
        pair = PartPair(
            part="P2",
            dxf_path=None,  # type: ignore[arg-type]
            sym_path=None,  # type: ignore[arg-type]
            dxf_rows=[
                {
                    "type": "LINE",
                    "normalized_start": [1.0, 0.0],
                    "normalized_end": [2.0, 0.0],
                }
            ],
            ddc_rows=[
                {
                    "tokens": [
                        encode_ddc_number_fraction(Fraction(1000000001, 1000000000)),
                        "",
                        encode_ddc_number_fraction(Fraction(1, 1)),
                        "",
                    ]
                }
            ],
        )
        observations = _coordinate_point_observations_for_pair(pair)
        model = {
            "coordinate_lookup": {},
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "coordinate_point_observations": observations,
            "context_coordinate_lookup": _build_context_coordinate_lookup(observations),
            "same_part_coordinate_lookup": _build_same_part_coordinate_lookup(observations),
            "token_observations": [],
            "token_lookup": {},
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row=pair.dxf_rows[0],
            dxf_rows=pair.dxf_rows,
            row_index=0,
            template_ddc_row={"tokens": ["", "", "", ""]},
            model=model,
            coordinate_resolver="context",
            prefer_literal_geometry=True,
        )

        self.assertEqual(tokens[0], encode_ddc_number_fraction(Fraction(1, 1)))
        self.assertEqual(slot_reports[0]["coordinate_source"], "literal_dyadic_line")

    def test_prefer_literal_geometry_uses_raw_noncardinal_arc_points(self) -> None:
        pair = PartPair(
            part="P2",
            dxf_path=None,  # type: ignore[arg-type]
            sym_path=None,  # type: ignore[arg-type]
            dxf_rows=[
                {
                    "type": "ARC",
                    "normalized_start_point": [1.000000001, 0.0],
                    "normalized_end_point": [1.0, 1.0],
                    "normalized_center": [0.0, 0.0],
                    "radius": 1.0,
                    "start_angle": 12.0,
                    "end_angle": 88.0,
                }
            ],
            ddc_rows=[
                {
                    "tokens": [
                        encode_ddc_number_fraction(Fraction(1, 1)),
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                }
            ],
        )
        observations = _coordinate_point_observations_for_pair(pair)
        model = {
            "coordinate_lookup": {},
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "coordinate_point_observations": observations,
            "context_coordinate_lookup": _build_context_coordinate_lookup(observations),
            "same_part_coordinate_lookup": _build_same_part_coordinate_lookup(observations),
            "token_observations": [],
            "token_lookup": {},
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row=pair.dxf_rows[0],
            dxf_rows=pair.dxf_rows,
            row_index=0,
            template_ddc_row={"tokens": ["", "", "", "", "", ""]},
            model=model,
            coordinate_resolver="context",
            prefer_literal_geometry=True,
        )

        self.assertEqual(tokens[0], encode_ddc_number_fraction(Fraction("1.000000001")))
        self.assertEqual(slot_reports[0]["coordinate_source"], "literal_raw_noncardinal_arc")

    def test_slot_value_fraction_lookup_can_override_line_delta(self) -> None:
        learned_fraction = Fraction(299999999, 100000000)
        model = {
            "coordinate_lookup": {},
            "coordinate_entries": [],
            "coordinate_fallback_lookup": {},
            "token_observations": [],
            "token_lookup": {},
            "slot_fraction_lookup": {
                "type_role_value": {
                    ("LINE", "delta_x", "3.000000"): [("P2", learned_fraction)],
                },
                "role_value": {},
                "value": {},
            },
            "value_digits": 6,
        }

        tokens, slot_reports = predict_geometry_tokens(
            target_part="P1",
            dxf_row={
                "type": "LINE",
                "normalized_start": [1.0, 0.0],
                "normalized_end": [4.0, 0.0],
            },
            template_ddc_row={"tokens": ["", "", "", ""]},
            model=model,
            use_slot_value_fractions=True,
        )

        self.assertEqual(tokens[2], encode_ddc_number_fraction(learned_fraction))
        self.assertIn("slot_fraction:type_role_value", slot_reports[2]["coordinate_source"])

    def test_replace_template_geometry_only_changes_geometry_data_field(self) -> None:
        template = """<RadanFile extension="ddc"><![CDATA[A,1,
G,,1,3,,1,,,1,,old.geometry,.,,,
C,$
]]></RadanFile>"""

        replaced = _replace_template_geometry(template, ["new.geometry"])

        self.assertIn("G,,1,3,,1,,,1,,new.geometry,.,,,", replaced)
        self.assertIn("A,1,", replaced)

    def test_compare_tokens_counts_exact_and_decoded_close(self) -> None:
        token = encode_ddc_number_fraction(Fraction(1, 8))
        result = _compare_tokens([token, ""], [token, ""])

        self.assertEqual(result["total_slots"], 2)
        self.assertEqual(result["exact_slots"], 2)
        self.assertEqual(result["decoded_close_1e_12_slots"], 2)


if __name__ == "__main__":
    unittest.main()
