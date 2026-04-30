import unittest

from analyze_sym_variant_tokens import _classify_slots, _compare_rows


class AnalyzeSymVariantTokensTests(unittest.TestCase):
    def test_compare_rows_counts_exact_decoded_and_changed_slots(self):
        left = [{"record": "G", "tokens": ["", "m?0"]}]
        right = [{"record": "G", "tokens": ["", "o?0"]}]

        result = _compare_rows(left, right, example_limit=5)

        self.assertEqual(result["total_slots"], 2)
        self.assertEqual(result["exact_slots"], 1)
        self.assertEqual(result["changed_slot_count"], 1)
        self.assertEqual(result["changed_rows"], [1])
        self.assertEqual(result["changed_slots_by_record_slot"], [{"record_slot": "G1", "count": 1}])
        self.assertGreater(result["max_decoded_abs_diff"], 0.0)
        self.assertEqual(result["decoded_nonclose_examples"][0]["slot"], 1)
        self.assertEqual(result["top_decoded_abs_diff_slots"][0]["slot"], 1)

    def test_classify_slots_splits_pass_and_fail_variants(self):
        variants = {
            "raw": [{"record": "G", "tokens": ["m?0"]}],
            "exported": [{"record": "G", "tokens": ["m?0"]}],
            "rounded": [{"record": "G", "tokens": ["o?0"]}],
        }

        result = _classify_slots(
            variants,
            pass_names={"raw", "exported"},
            fail_names={"rounded"},
            example_limit=5,
        )

        self.assertEqual(result["class_counts"], {"pass_fail_split": 1})
        self.assertEqual(result["examples"][0]["row_index"], 1)
        self.assertEqual(result["examples"][0]["slot"], 0)


if __name__ == "__main__":
    unittest.main()
