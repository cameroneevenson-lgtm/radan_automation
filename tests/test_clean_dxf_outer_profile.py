from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ezdxf

from clean_dxf_outer_profile import (
    Point2,
    clean_outer_profile,
    preprocessed_output_paths,
    simplify_closed_vertices,
    simplify_open_vertices,
)


class CleanDxfOuterProfileTests(unittest.TestCase):
    def test_simplify_closed_vertices_removes_tiny_stair_step(self) -> None:
        vertices = [
            Point2(0.0, 0.0),
            Point2(10.0, 0.0),
            Point2(10.0, 1.0),
            Point2(10.002, 1.0),
            Point2(10.002, 1.002),
            Point2(10.0, 1.002),
            Point2(10.0, 5.0),
            Point2(0.0, 5.0),
        ]

        simplified, stats = simplify_closed_vertices(vertices, tolerance=0.003)

        self.assertLess(len(simplified), len(vertices))
        self.assertGreater(stats["removed_vertices"], 0)
        self.assertLessEqual(stats["max_final_vertex_deviation"], 0.003)

    def test_simplify_open_vertices_preserves_endpoints(self) -> None:
        vertices = [
            Point2(0.0, 0.0),
            Point2(1.0, 0.0),
            Point2(1.002, 0.001),
            Point2(2.0, 0.0),
        ]

        simplified, stats = simplify_open_vertices(vertices, tolerance=0.003)

        self.assertEqual(simplified[0], vertices[0])
        self.assertEqual(simplified[-1], vertices[-1])
        self.assertGreater(stats["removed_vertices"], 0)

    def test_clean_outer_profile_rewrites_only_largest_line_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "source.dxf"
            out_path = root / "cleaned.dxf"
            doc = ezdxf.new("R2010")
            modelspace = doc.modelspace()
            outer = [
                (0.0, 0.0),
                (10.0, 0.0),
                (10.0, 1.0),
                (10.002, 1.0),
                (10.002, 1.002),
                (10.0, 1.002),
                (10.0, 5.0),
                (0.0, 5.0),
            ]
            inner = [(2.0, 2.0), (3.0, 2.0), (3.0, 3.0), (2.0, 3.0)]
            for loop in (outer, inner):
                for index, start in enumerate(loop):
                    end = loop[(index + 1) % len(loop)]
                    modelspace.add_line((*start, 0.0), (*end, 0.0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
            doc.saveas(dxf_path)

            payload = clean_outer_profile(dxf_path=dxf_path, out_path=out_path, simplify_tolerance=0.003)
            cleaned = ezdxf.readfile(out_path)
            line_count = sum(1 for entity in cleaned.modelspace() if entity.dxftype() == "LINE")

        self.assertTrue(payload["wrote_output"])
        self.assertEqual(payload["loop_count"], 2)
        self.assertLess(payload["simplification"]["output_vertices"], payload["simplification"]["input_vertices"])
        self.assertEqual(line_count, 4 + payload["simplification"]["output_vertices"])

    def test_clean_outer_profile_preserves_arcs_and_simplifies_line_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "source.dxf"
            out_path = root / "cleaned.dxf"
            doc = ezdxf.new("R2010")
            modelspace = doc.modelspace()
            layer = "IV_INTERIOR_PROFILES"
            modelspace.add_line((0.0, 0.0, 0.0), (5.0, 0.0, 0.0), dxfattribs={"layer": layer})
            modelspace.add_arc(
                center=(5.0, 1.0, 0.0),
                radius=1.0,
                start_angle=270.0,
                end_angle=0.0,
                dxfattribs={"layer": layer},
            )
            right_side = [
                (6.0, 1.0),
                (6.0, 2.0),
                (6.002, 2.0),
                (6.002, 2.002),
                (6.0, 2.002),
                (6.0, 4.0),
            ]
            for index, start in enumerate(right_side[:-1]):
                end = right_side[index + 1]
                modelspace.add_line((*start, 0.0), (*end, 0.0), dxfattribs={"layer": layer})
            modelspace.add_arc(
                center=(5.0, 4.0, 0.0),
                radius=1.0,
                start_angle=0.0,
                end_angle=90.0,
                dxfattribs={"layer": layer},
            )
            modelspace.add_line((5.0, 5.0, 0.0), (0.0, 5.0, 0.0), dxfattribs={"layer": layer})
            modelspace.add_line((0.0, 5.0, 0.0), (0.0, 0.0, 0.0), dxfattribs={"layer": layer})
            doc.saveas(dxf_path)

            payload = clean_outer_profile(dxf_path=dxf_path, out_path=out_path, simplify_tolerance=0.003)
            cleaned = ezdxf.readfile(out_path)
            arc_count = sum(1 for entity in cleaned.modelspace() if entity.dxftype() == "ARC")
            line_count = sum(1 for entity in cleaned.modelspace() if entity.dxftype() == "LINE")

        self.assertTrue(payload["wrote_output"])
        self.assertEqual(payload["selected_outside_entity_types"], ["ARC", "LINE"])
        self.assertEqual(payload["simplification"]["mode"], "arc_preserving_mixed_line_cleanup")
        self.assertGreater(payload["simplification"]["removed_vertices"], 0)
        self.assertEqual(arc_count, 2)
        self.assertLess(line_count, 8)

    def test_clean_outer_profile_refuses_w_drive_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_path = Path(tmpdir) / "source.dxf"
            doc = ezdxf.new("R2010")
            modelspace = doc.modelspace()
            points = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
            for index, start in enumerate(points):
                end = points[(index + 1) % len(points)]
                modelspace.add_line((*start, 0.0), (*end, 0.0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
            doc.saveas(dxf_path)

            with self.assertRaisesRegex(RuntimeError, "Refusing to write cleaned DXF on W:"):
                clean_outer_profile(dxf_path=dxf_path, out_path=Path(r"W:\LASER\cleaned.dxf"))

    def test_project_folder_writes_preprocessed_copy_and_report_under_l_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "F54410-B-49.dxf"
            project_folder = root / "L" / "F54410 PAINT PACK"
            project_folder.mkdir(parents=True)
            doc = ezdxf.new("R2010")
            modelspace = doc.modelspace()
            points = [
                (0.0, 0.0),
                (10.0, 0.0),
                (10.0, 1.0),
                (10.002, 1.0),
                (10.002, 1.002),
                (10.0, 1.002),
                (10.0, 5.0),
                (0.0, 5.0),
            ]
            for index, start in enumerate(points):
                end = points[(index + 1) % len(points)]
                modelspace.add_line((*start, 0.0), (*end, 0.0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
            doc.saveas(dxf_path)

            payload = clean_outer_profile(
                dxf_path=dxf_path,
                project_folder=project_folder,
                simplify_tolerance=0.002,
            )
            cleaned_path, report_path = preprocessed_output_paths(
                dxf_path=dxf_path,
                project_folder=project_folder,
                tolerance=0.002,
            )

            self.assertEqual(Path(payload["out_path"]), cleaned_path)
            self.assertEqual(cleaned_path.parent.name, "_preprocessed_dxfs")
            self.assertTrue(cleaned_path.exists())
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
