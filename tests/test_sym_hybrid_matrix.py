from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from sym_hybrid_matrix import _merge_geometry_lines


class SymHybridMatrixTests(unittest.TestCase):
    def test_merge_geometry_lines_preserves_base_crlf_trailing_newline(self) -> None:
        base = "A,1,\r\nG,,,,,,,,,,base1\r\nN,,cache\r\nH,,,,,,,,,,base2\r\n"
        source = "A,1,\nG,,,,,,,,,,src1\nH,,,,,,,,,,src2\n"

        merged = _merge_geometry_lines(base, source)

        self.assertEqual(merged, "A,1,\r\nG,,,,,,,,,,src1\r\nN,,cache\r\nH,,,,,,,,,,src2\r\n")

    def test_merge_geometry_lines_preserves_base_lf_without_trailing_newline(self) -> None:
        base = "A,1,\nG,,,,,,,,,,base1"
        source = "A,1,\r\nG,,,,,,,,,,src1\r\n"

        merged = _merge_geometry_lines(base, source)

        self.assertEqual(merged, "A,1,\nG,,,,,,,,,,src1")


if __name__ == "__main__":
    unittest.main()
