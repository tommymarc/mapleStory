import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QComboBox, QDialog

from src.main import configure_light_ui


class LightPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_light_ui(cls.app)

    def test_top_level_dialog_uses_light_background(self):
        dialog = QDialog()
        self.assertEqual(dialog.palette().color(QPalette.Window).name(), "#eef2f7")

    def test_combo_popup_uses_light_background(self):
        combo = QComboBox()
        combo.addItems(["普通路线", "辅助模式"])
        combo.show()
        combo.showPopup()
        self.app.processEvents()

        popup = combo.view().window()
        self.assertEqual(popup.palette().color(QPalette.Window).name(), "#eef2f7")
        self.assertEqual(combo.view().palette().color(QPalette.Base).name(), "#ffffff")

        combo.hidePopup()
        combo.close()


if __name__ == "__main__":
    unittest.main()
