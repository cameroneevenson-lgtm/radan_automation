from __future__ import annotations

import unittest

from batch_fix_parts_from_nest_live import (
    STATE_SYSTEM_SELECTED,
    _is_selected_state,
    _summarize_remap_payload,
)


class BatchFixPartsFromNestLiveTests(unittest.TestCase):
    def test_selected_state_is_bitmask_based(self) -> None:
        self.assertTrue(_is_selected_state(STATE_SYSTEM_SELECTED))
        self.assertTrue(_is_selected_state(STATE_SYSTEM_SELECTED | 0x100000))
        self.assertFalse(_is_selected_state(0))
        self.assertFalse(_is_selected_state("not-a-state"))

    def test_remap_summary_drops_large_success_result_list(self) -> None:
        summary = _summarize_remap_payload(
            {
                "session": {"process_id": 123},
                "candidate_count": 2,
                "success_count": 1,
                "failure_count": 1,
                "before": {"l": {"count": 2}},
                "after": {"l": {"count": 1}},
                "results": [
                    {"identifier": "/symbol editor/_1", "ok": True},
                    {"identifier": "/symbol editor/_2", "ok": False, "stage": "rfmac"},
                ],
            }
        )

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertNotIn("results", summary)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["failure_samples"], [{"identifier": "/symbol editor/_2", "ok": False, "stage": "rfmac"}])


if __name__ == "__main__":
    unittest.main()
