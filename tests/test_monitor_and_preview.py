import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import cv2
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSizePolicy

from src.ui.resource_tabs import load_route_preview_pixmap, preferred_monster_preview
from src.ui.ui import MainWindow, TAB_WINDOW_SIZE


class _ControllerStub:
    def __init__(self):
        self.viz_enabled = 0
        self.viz_disabled = 0

    def enable_bot_viz(self):
        self.viz_enabled += 1

    def disable_bot_viz(self):
        self.viz_disabled += 1


class MonitorAndPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_stand_frame_is_preferred_for_monster_preview(self):
        files = ["move_0.png", "hit1_0.png", "stand_0.png", "stand_1.png"]
        self.assertEqual(preferred_monster_preview(files), "stand_0.png")
        self.assertEqual(preferred_monster_preview(["move_0.png"]), "move_0.png")
        self.assertIsNone(preferred_monster_preview([]))

    def test_map_page_builds_a_polished_route_pixmap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = np.zeros((30, 42, 3), dtype=np.uint8)
            cv2.line(base, (4, 14), (37, 14), (130, 130, 130), 1)
            route = base.copy()
            cv2.line(route, (6, 14), (34, 14), (255, 0, 0), 1)
            map_path = os.path.join(directory, "map.png")
            route_path = os.path.join(directory, "route1.png")
            cv2.imwrite(map_path, base)
            cv2.imwrite(route_path, route)

            pixmap = load_route_preview_pixmap(route_path)

            self.assertFalse(pixmap.isNull())
            self.assertGreater(pixmap.width(), base.shape[1])

    def test_monitor_tab_is_next_to_log_and_enables_visualization(self):
        controller = _ControllerStub()
        window = MainWindow(controller)
        tabs = [window.tabs.tabText(index) for index in range(window.tabs.count())]

        log_index = tabs.index("运行日志")
        self.assertEqual(tabs[log_index + 1], "运行监控")
        self.assertEqual(
            window.debug_canvas.sizePolicy().horizontalPolicy(),
            QSizePolicy.Ignored,
        )

        window.tabs.setCurrentWidget(window.tab_game_window_viz)
        self.app.processEvents()
        self.assertEqual(controller.viz_enabled, 1)

        frame = np.zeros((180, 320, 3), dtype=np.uint8)
        window.update_debug_canvas(frame)
        self.assertFalse(window.debug_canvas.pixmap().isNull())

        route = np.zeros((240, 280, 3), dtype=np.uint8)
        route[80:84, 30:250] = (255, 80, 80)
        window.update_route_map_canvas(route)
        self.assertFalse(window.route_map_canvas.pixmap().isNull())
        self.assertTrue(window.tab_game_window_viz.isAncestorOf(window.tab_route_map_viz))

        window.deleteLater()

    def test_attack_fields_wrap_to_a_second_row(self):
        window = MainWindow(_ControllerStub())
        index = window.home_attack_grid.indexOf(
            window.home_aoe_trigger_count_field
        )
        row, column, _row_span, _column_span = \
            window.home_attack_grid.getItemPosition(index)

        self.assertEqual((row, column), (1, 0))
        self.assertEqual(TAB_WINDOW_SIZE["首页"][0], 700)
        self.assertLessEqual(TAB_WINDOW_SIZE["运行监控"][0], 1050)
        self.assertEqual(
            window.home_scroll_area.horizontalScrollBarPolicy(),
            Qt.ScrollBarAlwaysOff,
        )
        window.deleteLater()

if __name__ == "__main__":
    unittest.main()
