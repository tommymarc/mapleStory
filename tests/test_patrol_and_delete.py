# -*- coding: utf-8 -*-
"""Tests for patrol.yaml I/O and rope delete_edge."""
import os
import tempfile
import unittest

from src.utils.patrol import (
    load_patrol,
    merge_patrol_into_smart_patrol,
    save_patrol,
)
from src.utils.ropes import append_edge, delete_edge, load_ropes


class PatrolIoTests(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "patrol.yaml")
            save_patrol(
                "duoluozhuyi-xia",
                {
                    "map": "duoluozhuyi-xia",
                    "range": [0.2, 0.8],
                    "preferred_y": 22.5,
                    "preferred_y_tol": 10,
                    "rope_enable": False,
                },
                path=path,
            )
            doc = load_patrol("duoluozhuyi-xia", path=path)
            self.assertEqual(doc["range"], [0.2, 0.8])
            self.assertEqual(doc["preferred_y"], 22.5)
            self.assertFalse(doc["rope_enable"])

    def test_merge_only_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "missing.yaml")
            base = {"range": [0.1, 0.9], "rope_enable": True, "preferred_y": None}
            merged = merge_patrol_into_smart_patrol(base, "m", path=missing)
            self.assertEqual(merged["range"], [0.1, 0.9])
            path = os.path.join(tmp, "patrol.yaml")
            save_patrol("m", {"range": [0.25, 0.75], "rope_enable": False, "preferred_y_tol": 8}, path=path)
            merged2 = merge_patrol_into_smart_patrol(base, "m", path=path)
            self.assertEqual(merged2["range"], [0.25, 0.75])
            self.assertFalse(merged2["rope_enable"])


class DeleteEdgeTests(unittest.TestCase):
    def test_delete_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ropes.yaml")
            append_edge("m", (1, 2), (3, 4), direction="up", path=path)
            append_edge("m", (5, 6), (7, 8), direction="down", path=path)
            doc = load_ropes("m", path=path)
            self.assertEqual(len(doc["edges"]), 2)
            self.assertTrue(delete_edge("m", "rope_1", path=path))
            doc = load_ropes("m", path=path)
            self.assertEqual(len(doc["edges"]), 1)
            self.assertEqual(doc["edges"][0]["id"], "rope_2")
            self.assertFalse(delete_edge("m", "nope", path=path))


if __name__ == "__main__":
    unittest.main()


class BoundaryRecorderHelpers(unittest.TestCase):
    def test_player_x_ratio_and_normalize(self):
        from src.utils.boundary_recorder import normalize_range, player_x_ratio

        self.assertAlmostEqual(player_x_ratio((50, 10), 100), 0.5)
        self.assertAlmostEqual(player_x_ratio((0, 0), 200), 0.0)
        self.assertAlmostEqual(player_x_ratio((200, 0), 100), 1.0)
        self.assertIsNone(player_x_ratio(None, 100))
        self.assertEqual(normalize_range(0.8, 0.2), [0.2, 0.8])
        self.assertEqual(normalize_range(-1, 2), [0.0, 1.0])

    def test_delete_route_rejects_map_png(self):
        import tempfile
        from src.ui.resource_tabs import ResourceRepository

        with tempfile.TemporaryDirectory() as tmp:
            map_png = os.path.join(tmp, "map.png")
            open(map_png, "wb").close()
            repo = ResourceRepository.__new__(ResourceRepository)
            with self.assertRaises(ValueError):
                ResourceRepository.delete_route(repo, map_png)

            route = os.path.join(tmp, "route1.png")
            open(route, "wb").close()
            ResourceRepository.delete_route(repo, route)
            self.assertFalse(os.path.isfile(route))
