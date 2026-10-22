# Standard Import
import os
import sys
from pathlib import Path


def set_application_working_directory():
    """Run relative file access from the application directory.

    Config lives under config/; static game resources under assets/.
    A packaged executable may be launched from a shortcut or another
    working directory, so make its own directory the working directory first.
    """
    if getattr(sys, "frozen", False):
        application_dir = Path(sys.executable).resolve().parent
    else:
        application_dir = Path(__file__).resolve().parents[1]
    os.chdir(application_dir)


set_application_working_directory()

# PySide
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

# Load Import
from src.ui.ui import MainWindow
from src.ui.AutoBotController import AutoBotController


def configure_light_ui(app):
    """Apply a stable light palette to top-level dialogs and popup windows."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#eef2f7"))
    palette.setColor(QPalette.WindowText, QColor("#1f2937"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1e293b"))
    palette.setColor(QPalette.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.Text, QColor("#1f2937"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#334155"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor("#4f46e5"))
    palette.setColor(QPalette.Highlight, QColor("#4f46e5"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.PlaceholderText, QColor("#94a3b8"))
    palette.setColor(QPalette.Light, QColor("#ffffff"))
    palette.setColor(QPalette.Midlight, QColor("#e2e8f0"))
    palette.setColor(QPalette.Mid, QColor("#cbd5e1"))
    palette.setColor(QPalette.Dark, QColor("#94a3b8"))
    palette.setColor(QPalette.Shadow, QColor("#64748b"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#94a3b8"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#94a3b8"))
    app.setPalette(palette)


def main():
    '''
    Main Function
    Run: python -m ui.main
    '''
    # Native Windows dialogs and combo popups can inherit the OS dark theme.
    # Use Qt-rendered dialogs so every popup follows the application's palette.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    app = QApplication(sys.argv)
    configure_light_ui(app)

    autoBotController = AutoBotController()
    ui = MainWindow(autoBotController)

    autoBotController.update_signal(ui)

    ui.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
