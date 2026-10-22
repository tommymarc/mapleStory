import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication, QPushButton

from src.ui.nametag_picker import NametagPickerPopup
from src.ui.ui import MainWindow
from src.utils.image_io import write_image
from src.utils.nametag import (
    delete_saved_nametag,
    list_saved_nametags,
    nametag_image_path,
    safe_nametag_name,
)


class _ControllerStub:
    def enable_bot_viz(self):
        pass

    def disable_bot_viz(self):
        pass


def _write_nametag(directory, name, color=(200, 178, 120)):
    image = np.full((16, 72, 3), color, dtype=np.uint8)
    path = nametag_image_path(name, directory)
    write_image(path, image)
    return path


class SavedNametagCatalogTests(unittest.TestCase):
    def test_lists_newest_first_and_skips_example(self):
        with tempfile.TemporaryDirectory() as directory:
            _write_nametag(directory, "example")
            older = _write_nametag(directory, "雀雀被雷电")
            time.sleep(0.05)
            newer = _write_nametag(directory, "风吹雀雀很凉")

            names = [name for name, path in list_saved_nametags(directory)]
            self.assertEqual(names, ["风吹雀雀很凉", "雀雀被雷电"])
            self.assertTrue(os.path.isfile(older))
            self.assertTrue(os.path.isfile(newer))

    def test_delete_removes_matching_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write_nametag(directory, "风吹雀雀很凉")
            removed = delete_saved_nametag("风吹雀雀很凉", directory)
            self.assertEqual(removed, path)
            self.assertFalse(os.path.exists(path))

    def test_safe_name_keeps_chinese_characters(self):
        self.assertEqual(safe_nametag_name(" 风吹雀雀很凉 "), "风吹雀雀很凉")


class NametagPickerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_select_and_delete_history_from_home_page(self):
        window = MainWindow(_ControllerStub())
        with tempfile.TemporaryDirectory() as directory:
            window.nametag_dir = directory
            _write_nametag(directory, "雀雀被雷电")
            _write_nametag(directory, "风吹雀雀很凉")

            self.assertTrue(window.apply_character_nametag("风吹雀雀很凉"))
            self.assertEqual(window.character_name_edit.text(), "风吹雀雀很凉")
            self.assertEqual(window.cfg["nametag"]["name"], "风吹雀雀很凉")
            self.assertTrue(window.cfg["nametag"]["enable"])

            picker = window._ensure_nametag_picker()
            picker.populate(list_saved_nametags(directory), "风吹雀雀很凉")
            names = [
                picker.list_layout.itemAt(index).widget().name
                for index in range(picker.list_layout.count())
                if picker.list_layout.itemAt(index).widget() is not None
                and hasattr(picker.list_layout.itemAt(index).widget(), "name")
            ]
            self.assertIn("风吹雀雀很凉", names)
            self.assertIn("雀雀被雷电", names)

            self.assertTrue(window.delete_character_nametag("风吹雀雀很凉"))
            self.assertFalse(
                os.path.exists(nametag_image_path("风吹雀雀很凉", directory))
            )
            self.assertEqual(window.character_name_edit.text(), "")
            self.assertFalse(window.cfg["nametag"]["enable"])

        window.deleteLater()

    def test_picker_row_delete_button_does_not_select(self):
        popup = NametagPickerPopup()
        with tempfile.TemporaryDirectory() as directory:
            path = _write_nametag(directory, "雀雀被雷电")
            selected = []
            deleted = []
            popup.nametag_selected.connect(selected.append)
            popup.nametag_deleted.connect(deleted.append)
            popup.populate([("雀雀被雷电", path)], "")

            row = popup.list_layout.itemAt(0).widget()
            delete_button = row.findChild(QPushButton, "nametagDeleteButton")
            delete_button.click()

        self.assertEqual(deleted, ["雀雀被雷电"])
        self.assertEqual(selected, [])
        popup.deleteLater()


if __name__ == "__main__":
    unittest.main()
