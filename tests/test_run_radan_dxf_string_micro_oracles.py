from __future__ import annotations

import unittest

from run_radan_dxf_string_micro_oracles import _apply_variant_mutations, _mutate_group_value


class RadanDxfStringMicroOracleTests(unittest.TestCase):
    def test_mutate_group_value_rewrites_only_matching_group_code_value_pairs(self) -> None:
        text = " 10\n0.025000\n 20\n0.025000\n 40\n0.025000\n"

        mutated = _mutate_group_value(
            text,
            group_code="40",
            source_value="0.025000",
            target_value="0.025000000001",
        )

        self.assertEqual(mutated, " 10\n0.025000\n 20\n0.025000\n 40\n0.025000000001\n")

    def test_apply_variant_mutations_can_combine_plain_and_group_replacements(self) -> None:
        text = " 10\n2.024219\n 20\n0.025000\n 40\n0.025000\n"

        mutated = _apply_variant_mutations(
            text,
            {
                "replacements": {"2.024219": "2.024219000001"},
                "group_value_replacements": [
                    {"group_code": "40", "source_value": "0.025000", "target_value": "0.025000000001"}
                ],
            },
        )

        self.assertEqual(mutated, " 10\n2.024219000001\n 20\n0.025000\n 40\n0.025000000001\n")


if __name__ == "__main__":
    unittest.main()
