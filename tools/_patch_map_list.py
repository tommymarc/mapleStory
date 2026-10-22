# -*- coding: utf-8 -*-
from pathlib import Path

path = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\resource_tabs.py")
text = path.read_text(encoding="utf-8")

old_import = "from PySide6.QtCore import QThread, Qt, QUrl, Signal"
new_import = "from PySide6.QtCore import QThread, Qt, QUrl, QSize, Signal"
if old_import not in text:
    raise SystemExit("import line not found")
text = text.replace(old_import, new_import, 1)

old_list = (
    "        self.map_list = QListWidget()\n"
    "        self.map_list.currentItemChanged.connect(self._on_map_changed)\n"
    "        layout.addWidget(self.map_list, 1)"
)

new_list = (
    "        self.map_list = QListWidget()\n"
    "        self.map_list.setObjectName(\"mapList\")\n"
    "        # Custom item widgets need zero ::item padding; global stylesheet padding\n"
    "        # would shrink the widget rect and clip label/button glyphs mid-height.\n"
    "        self.map_list.setStyleSheet(\n"
    "            \"\"\"\n"
    "            QListWidget#mapList::item {\n"
    "                min-height: 44px;\n"
    "                padding: 0px;\n"
    "                margin: 2px 0;\n"
    "                border-radius: 7px;\n"
    "            }\n"
    "            QListWidget#mapList::item:hover {\n"
    "                background-color: #f0efff;\n"
    "            }\n"
    "            QListWidget#mapList::item:selected {\n"
    "                background-color: #6657d9;\n"
    "            }\n"
    "            \"\"\"\n"
    "        )\n"
    "        self.map_list.currentItemChanged.connect(self._on_map_changed)\n"
    "        layout.addWidget(self.map_list, 1)"
)

if old_list not in text:
    raise SystemExit("map_list block not found")
text = text.replace(old_list, new_list, 1)

old_row = (
    "            item = QListWidgetItem()\n"
    "            item.setData(Qt.UserRole, name)\n"
    "            row = QWidget()\n"
    "            row_layout = QHBoxLayout(row)\n"
    "            row_layout.setContentsMargins(8, 4, 8, 4)\n"
    "            row_layout.setSpacing(8)\n"
    "            label = QLabel(f\"🗺 {self.repository.display_name(name)}{suffix}\")\n"
    "            label.setStyleSheet(\"color: #1e293b;\")\n"
    "            manage_btn = QPushButton(\"管理\")\n"
    "            manage_btn.setFixedWidth(72)\n"
    "            manage_btn.clicked.connect(lambda _checked=False, n=name: self._open_manage(n))\n"
    "            row_layout.addWidget(label, 1)\n"
    "            row_layout.addWidget(manage_btn)\n"
    "            row.adjustSize()\n"
    "            item.setSizeHint(row.sizeHint())\n"
    "            self.map_list.addItem(item)\n"
    "            self.map_list.setItemWidget(item, row)"
)

new_row = (
    "            item = QListWidgetItem()\n"
    "            item.setData(Qt.UserRole, name)\n"
    "            row = QWidget()\n"
    "            row.setMinimumHeight(44)\n"
    "            row_layout = QHBoxLayout(row)\n"
    "            row_layout.setContentsMargins(10, 6, 10, 6)\n"
    "            row_layout.setSpacing(8)\n"
    "            row_layout.setAlignment(Qt.AlignVCenter)\n"
    "            label = QLabel(f\"🗺 {self.repository.display_name(name)}{suffix}\")\n"
    "            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)\n"
    "            label.setStyleSheet(\"color: #1e293b; background: transparent;\")\n"
    "            manage_btn = QPushButton(\"管理\")\n"
    "            manage_btn.setFixedSize(72, 30)\n"
    "            manage_btn.setStyleSheet(\n"
    "                \"min-height: 0; padding: 4px 10px; font-weight: 600;\"\n"
    "            )\n"
    "            manage_btn.clicked.connect(lambda _checked=False, n=name: self._open_manage(n))\n"
    "            row_layout.addWidget(label, 1)\n"
    "            row_layout.addWidget(manage_btn, 0, Qt.AlignVCenter)\n"
    "            hint = row.sizeHint()\n"
    "            item.setSizeHint(QSize(max(hint.width(), 120), max(44, hint.height())))\n"
    "            self.map_list.addItem(item)\n"
    "            self.map_list.setItemWidget(item, row)"
)

if old_row not in text:
    raise SystemExit("refresh_maps row block not found")
text = text.replace(old_row, new_row, 1)

path.write_text(text, encoding="utf-8")
print("resource_tabs.py patched OK")
