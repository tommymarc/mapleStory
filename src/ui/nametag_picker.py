"""Dropdown popup for previously imported character nametag images."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class NametagPickerRow(QFrame):
    selected = Signal(str)
    deleted = Signal(str)

    def __init__(self, name, image_path, is_current=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("nametagPickerRow")
        self.setProperty("current", is_current)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 6, 6)
        layout.setSpacing(8)

        preview = QLabel()
        preview.setObjectName("nametagPickerThumb")
        preview.setFixedSize(84, 24)
        preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            preview.setText("无图")
        else:
            preview.setPixmap(
                pixmap.scaled(
                    preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        layout.addWidget(preview)

        name_label = QLabel(name)
        name_label.setObjectName("nametagPickerName")
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(name_label, 1)

        delete_button = QPushButton("×")
        delete_button.setObjectName("nametagDeleteButton")
        delete_button.setFixedSize(24, 24)
        delete_button.setCursor(Qt.PointingHandCursor)
        delete_button.setToolTip(f"删除“{name}”")
        delete_button.clicked.connect(self._emit_deleted)
        layout.addWidget(delete_button)

    def _emit_deleted(self):
        self.deleted.emit(self.name)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.name)
            event.accept()
            return
        super().mousePressEvent(event)


class NametagPickerPopup(QFrame):
    nametag_selected = Signal(str)
    nametag_deleted = Signal(str)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("nametagPickerPopup")
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("历史角色名")
        title.setObjectName("nametagPickerTitle")
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll)

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.scroll.setWidget(self.list_host)

    def populate(self, items, current_name=""):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not items:
            empty = QLabel("还没有导入过角色名图片")
            empty.setObjectName("nametagPickerEmpty")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            self.scroll.setFixedHeight(72)
            return

        for name, path in items:
            row = NametagPickerRow(name, path, is_current=(name == current_name))
            row.selected.connect(self._select_nametag)
            row.deleted.connect(self.nametag_deleted.emit)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)
        self.scroll.setFixedHeight(min(240, 16 + 40 * len(items)))

    def _select_nametag(self, name):
        self.nametag_selected.emit(name)
        self.close()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()

    def show_below(self, anchor):
        width = max(anchor.width(), 280)
        self.setFixedWidth(width)
        self.adjustSize()
        origin = anchor.mapToGlobal(anchor.rect().bottomLeft())
        self.move(origin)
        self.show()
        self.raise_()
