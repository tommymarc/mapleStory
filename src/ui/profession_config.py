"""Profession profiles and visual keyboard configuration UI."""

import os
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.utils.common import load_yaml, save_yaml
from src.utils.profession_bindings import apply_profession_profile, BUFF_SLOT_RE
from src.utils.ui import ModernSpinBox, SingleKeyEdit


FUNCTION_DEFINITIONS = [
    ("clear", "清除", "#cbd5e1", False),
    ("main_attack", "主攻", "#ff7568", False),
    ("aoe_attack", "群攻（范围攻击）", "#d946ef", False),
    ("secondary_attack_1", "副攻1", "#43c1c7", False),
    ("secondary_attack_2", "副攻2", "#39a9d0", False),
    ("secondary_attack_3", "副攻3", "#91cdb8", False),
    ("secondary_attack_4", "副攻4", "#ffc864", False),
    ("secondary_attack_5", "副攻5", "#9891f2", False),
    ("secondary_attack_6", "副攻6", "#f77aa4", False),
    ("secondary_attack_7", "副攻7", "#675ae8", False),
    ("secondary_attack_8", "副攻8", "#08b5c3", False),
    ("jump", "跳跃", "#08aa9d", False),
    ("dialog", "对话", "#ef784b", False),
    ("x_axis_movement", "X轴位移", "#ff7568", False),
    ("add_hp", "加血", "#f04491", False),
    ("add_mp", "加蓝", "#1769eb", False),
    ("buff", "BUFF", "#f59e0b", True),
    ("pet_food", "宠物喂食", "#84cc16", True),
    ("experience_coupon", "经验券", "#119fa8", True),
]

FUNCTION_BY_ID = {
    function_id: {
        "label": label,
        "color": color,
        "requires_interval": requires_interval,
    }
    for function_id, label, color, requires_interval in FUNCTION_DEFINITIONS
}

KEYBOARD_ROWS = [
    ["esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"],
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "\\"],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'"],
    ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/"],
    ["shift", "ctrl", "alt", "space"],
]

NAVIGATION_KEYS = [
    ["insert", "home", "pageup"],
    ["delete", "end", "pagedown"],
    [None, "up", None],
    ["left", "down", "right"],
]

EXTRA_BUFF_COLORS = [
    "#fb923c", "#f59e0b", "#eab308", "#f97316", "#d97706", "#ca8a04",
]
MAX_EXTRA_BUFFS = 12


def extra_buff_meta(function_id):
    match = BUFF_SLOT_RE.fullmatch(str(function_id or ""))
    if not match:
        return None
    number = int(match.group(1))
    return {
        "label": f"BUFF{number}",
        "color": EXTRA_BUFF_COLORS[(number - 1) % len(EXTRA_BUFF_COLORS)],
        "requires_interval": True,
    }


def is_interval_function(function_id):
    if function_id in FUNCTION_BY_ID:
        return bool(FUNCTION_BY_ID[function_id]["requires_interval"])
    return extra_buff_meta(function_id) is not None


class FunctionChipWidget(QWidget):
    """Colored function chip; extra BUFF chips get a top-right remove control."""

    clicked = Signal()
    removed = Signal()

    def __init__(self, label, color, removable=False, parent=None):
        super().__init__(parent)
        self.setMinimumSize(104, 38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        text_color = readable_text_color(color)
        self.button = QPushButton(label, self)
        self.button.setProperty("functionChip", True)
        self.button.setMinimumSize(104, 38)
        self.button.setStyleSheet(
            "QPushButton {"
            f"background-color: {color}; color: {text_color}; "
            "border: 2px solid transparent; border-radius: 8px; font-weight: 700;"
            "}"
            "QPushButton:hover { border-color: #ffffff; }"
            "QPushButton:disabled { background-color: #e8edf4; color: #9aa7b8; }"
        )
        self.button.clicked.connect(self.clicked.emit)
        self.close_button = None
        if removable:
            self.close_button = QPushButton("×", self)
            self.close_button.setObjectName("chipRemoveButton")
            self.close_button.setFixedSize(16, 16)
            self.close_button.setCursor(Qt.PointingHandCursor)
            self.close_button.setToolTip("移除该 BUFF")
            self.close_button.clicked.connect(self.removed.emit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.button.setGeometry(0, 0, self.width(), self.height())
        if self.close_button is not None:
            self.close_button.move(max(0, self.width() - 16), 0)
            self.close_button.raise_()


KEY_DISPLAY = {
    "insert": "ins",
    "home": "hm",
    "pageup": "pup",
    "delete": "del",
    "pagedown": "pdn",
}


def readable_text_color(color):
    """Return a high-contrast foreground color for a hex background."""
    value = color.lstrip("#")
    red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return "#172033" if luminance > 0.62 else "#ffffff"


class ProfessionConfigStore:
    """Persist profession-specific keyboard bindings in YAML."""

    def __init__(self, path="config/config_professions.yaml"):
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            data = load_yaml(self.path)
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("version", 1)
        data.setdefault("selected_profession", "")
        data.setdefault("professions", {})
        self._migrate_legacy_bindings(data)
        self._ensure_builtin_profiles(data)
        return data

    @staticmethod
    def _migrate_legacy_bindings(data):
        """Preserve the old combined binding as BUFF, matching old runtime behavior."""
        professions = data.get("professions", {})
        if not isinstance(professions, dict):
            data["professions"] = {}
            professions = data["professions"]
        for profile in professions.values():
            if not isinstance(profile, dict):
                continue
            bindings = profile.setdefault("bindings", {})
            intervals = profile.setdefault("intervals", {})
            if not isinstance(bindings, dict):
                bindings = {}
                profile["bindings"] = bindings
            if not isinstance(intervals, dict):
                intervals = {}
                profile["intervals"] = intervals
            # Auto pickup was retired; discard its hidden binding when loading
            # profiles created by versions that briefly exposed the feature.
            bindings.pop("pickup", None)
            legacy_key = bindings.pop("buff_pet_food", "")
            if legacy_key and not bindings.get("buff"):
                bindings["buff"] = legacy_key
            legacy_interval = intervals.pop("buff_pet_food", None)
            intervals.setdefault("buff", int(legacy_interval or 60))
            intervals.setdefault("pet_food", 600)
            intervals.setdefault("experience_coupon", 3600)
        data["version"] = 2


    def _ensure_builtin_profiles(self, data):
        """Remove legacy 剑客 builtin if present; clear selection when it was 剑客."""
        professions = data.setdefault("professions", {})
        if not isinstance(professions, dict):
            data["professions"] = {}
            professions = data["professions"]
        if "剑客" in professions:
            professions.pop("剑客", None)
        if data.get("selected_profession") == "剑客":
            data["selected_profession"] = ""
        return data

    @staticmethod
    def empty_profile(attack_type="directional", bindings=None):
        return {
            "main_attack_type": attack_type,
            "jump_attack": False,
            "bindings": dict(bindings or {}),
            "intervals": {
                "buff": 60,
                "pet_food": 600,
                "experience_coupon": 3600,
            },
        }

    def save(self):
        save_yaml(self.data, self.path)

    def names(self):
        return list(self.data["professions"].keys())

    def selected_name(self):
        name = self.data.get("selected_profession", "")
        return name if name in self.data["professions"] else ""

    def select(self, name):
        self.data["selected_profession"] = name if name in self.data["professions"] else ""

    def get(self, name):
        return self.data["professions"].get(name)

    def add(self, name, attack_type="directional", bindings=None):
        if not name or name in self.data["professions"]:
            return False
        unique_bindings = {}
        used_keys = set()
        for function_id, key in (bindings or {}).items():
            if key and key not in used_keys:
                unique_bindings[function_id] = key
                used_keys.add(key)
        self.data["professions"][name] = self.empty_profile(attack_type, unique_bindings)
        self.select(name)
        return True

    def delete(self, name):
        if name not in self.data["professions"]:
            return False
        del self.data["professions"][name]
        if self.data.get("selected_profession") == name:
            self.data["selected_profession"] = ""
        return True

    def reset(self, name):
        profile = self.get(name)
        if profile is None:
            return
        attack_type = profile.get("main_attack_type", "directional")
        self.data["professions"][name] = self.empty_profile(attack_type)

    def apply_to_cfg(self, cfg, name, fallback_cfg=None):
        """Map supported profession bindings to the existing engine config."""
        profile = self.get(name)
        apply_profession_profile(cfg, name, profile, fallback_cfg)


class AddProfessionDialog(QDialog):
    """Collect a profession name and the three most common initial bindings."""

    def __init__(self, existing_names, parent=None):
        super().__init__(parent)
        self.existing_names = set(existing_names)
        self.setWindowTitle("添加职业")
        self.setModal(True)
        self.setMinimumSize(430, 330)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入职业名")
        form.addRow("职业名：", self.name_edit)

        self.attack_type_combo = QComboBox()
        self.attack_type_combo.addItem("普通攻击", "directional")
        self.attack_type_combo.addItem("范围技能", "aoe_skill")
        self.attack_type_combo.addItem("混合攻击", "hybrid")
        form.addRow("主攻类型：", self.attack_type_combo)

        self.jump_key = SingleKeyEdit()
        self.main_attack_key = SingleKeyEdit()
        self.dialog_key = SingleKeyEdit()
        form.addRow("跳跃键：", self.jump_key)
        form.addRow("主攻技能键：", self.main_attack_key)
        form.addRow("对话键：", self.dialog_key)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("添加")
        buttons.button(QDialogButtonBox.Ok).setObjectName("dialogPrimaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)
        title = QLabel("创建职业配置")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #263449;")
        description = QLabel("先设置常用键位，其他技能可稍后在可视化键盘中补充。")
        description.setStyleSheet("color: #718096;")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "添加职业", "请输入职业名。")
            return
        if name in self.existing_names:
            QMessageBox.warning(self, "添加职业", "该职业已经存在。")
            return
        self.accept()

    def values(self):
        bindings = {}
        for function_id, editor in (
            ("jump", self.jump_key),
            ("main_attack", self.main_attack_key),
            ("dialog", self.dialog_key),
        ):
            key = editor.get_key()
            if key:
                bindings[function_id] = key
        return (
            self.name_edit.text().strip(),
            self.attack_type_combo.currentData(),
            bindings,
        )


class KeyboardConfigDialog(QDialog):
    """Visual keyboard editor for profession-specific bindings."""

    profiles_changed = Signal()

    def __init__(self, store, selected_profession="", parent=None):
        super().__init__(parent)
        self.store = store
        self.selected_key = None
        self.pending_function = None
        self.key_buttons = {}
        self.function_buttons = {}
        self.extra_buff_ids = []
        self.function_legend_grid = None
        self.add_buff_button = None
        self.setObjectName("keyboardConfigDialog")
        self.setWindowTitle("键盘配置")
        self.resize(1180, 900)
        self.setMinimumSize(960, 660)
        self.setStyleSheet(self._dialog_style_sheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)
        root.addWidget(self._build_header())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(14)

        profile_group = QGroupBox("职业配置")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setContentsMargins(16, 18, 16, 14)
        profile_layout.setSpacing(10)
        profile_layout.addLayout(self._build_profession_controls())
        profile_layout.addLayout(self._build_profile_options())
        content_layout.addWidget(profile_group)

        self.current_function_label.setObjectName("selectionStatus")
        self.current_function_label.setMinimumHeight(46)
        content_layout.addWidget(self.current_function_label)
        content_layout.addWidget(self._build_function_legend())
        content_layout.addWidget(self._build_keyboard())
        content_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("keyboardDialogScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidget(content)
        root.addWidget(scroll_area, 1)
        root.addLayout(self._build_footer())

        self._refresh_professions(selected_profession or self.store.selected_name())
        self._set_enabled_state()

    def _build_header(self):
        header = QFrame()
        header.setObjectName("keyboardDialogHeader")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(3)

        title = QLabel("职业键盘绑定")
        title.setObjectName("keyboardDialogTitle")
        subtitle = QLabel("选择一个功能与键位完成绑定；已绑定键位会显示对应颜色。")
        subtitle.setObjectName("keyboardDialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    @staticmethod
    def _dialog_style_sheet():
        return """
            QDialog {
                color: #1f2937;
                background-color: #eef2f7;
            }
            QDialog#keyboardConfigDialog {
                background-color: #eef2f7;
            }
            QFrame#keyboardDialogHeader {
                border: none;
                border-radius: 14px;
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #172554, stop: 0.52 #3730a3, stop: 1 #2563eb
                );
            }
            QLabel#keyboardDialogTitle {
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#keyboardDialogSubtitle {
                color: #eef2ff;
                font-size: 12px;
            }
            QLabel#selectionStatus {
                color: #3730a3;
                background-color: #eef2ff;
                border: 1px solid #c7d2fe;
                border-radius: 10px;
                padding: 8px 13px;
                font-weight: 600;
            }
            QScrollArea#keyboardDialogScroll {
                border: none;
                background-color: transparent;
            }
            QLineEdit, QComboBox, QSpinBox, QKeySequenceEdit {
                color: #1f2937;
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                min-height: 27px;
                padding: 6px 10px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QKeySequenceEdit:focus {
                border: 2px solid #4f46e5;
                padding: 5px 9px;
            }
            QComboBox {
                padding-right: 36px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 32px;
                border: none;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: #f8fafc;
            }
            QComboBox::drop-down:hover {
                background-color: #eef2ff;
            }
            QComboBoxPrivateContainer {
                background-color: #ffffff;
                border: 1px solid #cfd9e6;
                border-radius: 10px;
                padding: 4px;
            }
            QComboBox QAbstractItemView {
                color: #172033;
                background-color: #ffffff;
                border: none;
                border-radius: 6px;
                outline: none;
                padding: 2px;
                selection-color: #ffffff;
                selection-background-color: #766ee0;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 5px 10px;
                margin: 1px 0;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView::item:hover {
                color: #32267d;
                background-color: #e9e7ff;
                font-weight: 600;
            }
            QComboBox QAbstractItemView::item:selected {
                color: #ffffff;
                background-color: #766ee0;
                font-weight: 600;
            }
            QSpinBox {
                padding-right: 30px;
                font-weight: 600;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 25px;
                border: none;
                border-left: 1px solid #d6deea;
                border-bottom: 1px solid #d6deea;
                border-top-right-radius: 8px;
                background-color: #f1f5f9;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 25px;
                border: none;
                border-left: 1px solid #d6deea;
                border-bottom-right-radius: 8px;
                background-color: #f1f5f9;
            }
            QPushButton {
                color: #334155;
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                min-height: 28px;
                padding: 6px 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #3730a3;
                border-color: #818cf8;
                background-color: #eef2ff;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #dce3ec;
                border-radius: 14px;
                margin-top: 14px;
                padding-top: 8px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 7px;
                color: #334155;
                background-color: #ffffff;
            }
            QPushButton[functionChip="true"] {
                border: none;
                border-radius: 8px;
                padding: 6px 9px;
                font-weight: 700;
            }
            QPushButton[functionChip="true"]:hover {
                border: 2px solid #ffffff;
            }
            QPushButton#addBuffChipButton {
                color: #c2410c;
                background-color: #fff7ed;
                border: 2px dashed #fb923c;
                border-radius: 8px;
                padding: 6px 9px;
                font-weight: 700;
            }
            QPushButton#addBuffChipButton:hover {
                color: #9a3412;
                background-color: #ffedd5;
                border-color: #f97316;
            }
            QPushButton#chipRemoveButton {
                color: #ffffff;
                background-color: #b91c1c;
                border: 1px solid #ffffff;
                border-radius: 8px;
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
                padding: 0px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton#chipRemoveButton:hover {
                color: #ffffff;
                background-color: #dc2626;
                border-color: #ffffff;
            }
            QPushButton[keyboardKey="true"] {
                padding: 0;
            }
            QPushButton#dialogPrimaryButton {
                color: #ffffff;
                border: none;
                background-color: #4f46e5;
                min-width: 110px;
            }
            QPushButton#dialogPrimaryButton:hover {
                background-color: #4338ca;
            }
            QPushButton#dialogResetButton {
                color: #d14343;
                border-color: #efb0b0;
                background-color: #ffffff;
            }
            QPushButton#dialogResetButton:hover {
                color: #ffffff;
                border-color: #d14343;
                background-color: #d14343;
            }
        """

    def _build_profession_controls(self):
        layout = QHBoxLayout()
        layout.addWidget(QLabel("职业："))
        self.profession_combo = QComboBox()
        self.profession_combo.setMinimumWidth(150)
        self.profession_combo.currentTextChanged.connect(self._on_profession_changed)
        layout.addWidget(self.profession_combo)

        add_button = QPushButton("添加职业")
        add_button.setObjectName("secondaryActionButton")
        add_button.clicked.connect(self._add_profession)
        self.delete_button = QPushButton("删除职业")
        self.delete_button.setObjectName("dangerOutlineButton")
        self.delete_button.clicked.connect(self._delete_profession)
        layout.addWidget(add_button)
        layout.addWidget(self.delete_button)
        layout.addStretch(1)
        return layout

    def _build_profile_options(self):
        layout = QHBoxLayout()
        layout.addWidget(QLabel("主攻类型："))
        self.attack_type_combo = QComboBox()
        self.attack_type_combo.addItem("普通", "directional")
        self.attack_type_combo.addItem("范围技能", "aoe_skill")
        self.attack_type_combo.addItem("混合攻击", "hybrid")
        self.attack_type_combo.currentIndexChanged.connect(self._on_attack_type_changed)
        layout.addWidget(self.attack_type_combo)

        self.jump_attack_checkbox = QCheckBox("跳打模式")
        self.jump_attack_checkbox.setToolTip(
            "勾选后：移动中先断按跳跃，再随机延迟 0.04–0.15 秒断按主攻/群攻；方向键保持按住"
        )
        self.jump_attack_checkbox.stateChanged.connect(self._on_jump_attack_changed)
        layout.addWidget(self.jump_attack_checkbox)

        self.interval_container = QWidget()
        interval_layout = QHBoxLayout(self.interval_container)
        interval_layout.setContentsMargins(20, 0, 0, 0)
        self.interval_label = QLabel("BUFF间隔（秒）：")
        self.interval_spin = ModernSpinBox()
        self.interval_spin.setRange(1, 86400)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        interval_layout.addWidget(self.interval_label)
        interval_layout.addWidget(self.interval_spin)
        self.interval_container.setVisible(False)
        layout.addWidget(self.interval_container)
        layout.addStretch(1)

        self.current_function_label = QLabel("当前按键功能：无")
        return layout

    def _build_function_legend(self):
        group = QGroupBox("功能颜色 · 可先选功能，也可先选按键")
        self.function_legend_grid = QGridLayout(group)
        self.function_legend_grid.setContentsMargins(16, 18, 16, 14)
        self.function_legend_grid.setHorizontalSpacing(8)
        self.function_legend_grid.setVerticalSpacing(8)
        self._rebuild_function_chips()
        return group

    def _function_meta(self, function_id):
        if function_id in FUNCTION_BY_ID:
            return FUNCTION_BY_ID[function_id]
        return extra_buff_meta(function_id) or {}

    def _ordered_extra_buff_ids(self):
        ids = set(self.extra_buff_ids)
        profile = self._current_profile()
        if profile:
            for function_id in list(profile.get("bindings", {})) + list(
                profile.get("intervals", {})
            ):
                if BUFF_SLOT_RE.fullmatch(str(function_id)):
                    ids.add(str(function_id))
        return sorted(ids, key=lambda value: int(BUFF_SLOT_RE.fullmatch(value).group(1)))

    def _clear_function_legend_grid(self):
        grid = self.function_legend_grid
        if grid is None:
            return
        # takeAt + deleteLater leaves the old "+ buff" as an unparented-in-layout
        # child that still paints behind the keyboard / function cards.
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self.function_buttons = {}
        self.add_buff_button = None

    def _rebuild_function_chips(self):
        grid = self.function_legend_grid
        if grid is None:
            return
        self._clear_function_legend_grid()
        definitions = list(FUNCTION_DEFINITIONS)
        for function_id in self._ordered_extra_buff_ids():
            meta = extra_buff_meta(function_id)
            if meta:
                definitions.append(
                    (function_id, meta["label"], meta["color"], True)
                )
        for index, (function_id, label, color, _) in enumerate(definitions):
            removable = extra_buff_meta(function_id) is not None
            chip = FunctionChipWidget(label, color, removable=removable)
            chip.clicked.connect(
                lambda value=function_id: self._on_function_clicked(value)
            )
            if removable:
                chip.removed.connect(
                    lambda value=function_id: self._remove_extra_buff(value)
                )
            self.function_buttons[function_id] = chip.button
            grid.addWidget(chip, index // 6, index % 6)
        add_button = QPushButton("+ buff")
        add_button.setObjectName("addBuffChipButton")
        add_button.setMinimumSize(104, 38)
        add_button.setToolTip("添加 BUFF1、BUFF2、BUFF3… 可分别绑定按键和间隔")
        add_button.clicked.connect(self._add_buff_chip)
        add_index = len(definitions)
        grid.addWidget(add_button, add_index // 6, add_index % 6)
        self.add_buff_button = add_button
        enabled = self._current_profile() is not None
        add_button.setEnabled(enabled)
        for button in self.function_buttons.values():
            button.setEnabled(enabled)

    def _add_buff_chip(self):
        existing = set(self._ordered_extra_buff_ids())
        number = 1
        while f"buff{number}" in existing:
            number += 1
        if number > MAX_EXTRA_BUFFS:
            QMessageBox.warning(self, "BUFF", f"最多添加 {MAX_EXTRA_BUFFS} 个额外 BUFF。")
            return
        function_id = f"buff{number}"
        if function_id not in self.extra_buff_ids:
            self.extra_buff_ids.append(function_id)
        profile = self._current_profile()
        if profile is not None:
            profile.setdefault("intervals", {}).setdefault(function_id, 60)
        self._rebuild_function_chips()
        self._on_function_clicked(function_id)

    def _remove_extra_buff(self, function_id):
        if extra_buff_meta(function_id) is None:
            return
        self.extra_buff_ids = [
            item for item in self.extra_buff_ids if item != function_id
        ]
        profile = self._current_profile()
        if profile is not None:
            profile.setdefault("bindings", {}).pop(function_id, None)
            profile.setdefault("intervals", {}).pop(function_id, None)
        if self.pending_function == function_id:
            self.pending_function = None
            self.current_function_label.setText("当前按键功能：无")
            self.interval_container.setVisible(False)
        elif self.interval_spin.property("functionId") == function_id:
            self.interval_container.setVisible(False)
        self._rebuild_function_chips()
        self._set_enabled_state()
        self._refresh_keyboard()

    def _build_keyboard(self):
        group = QGroupBox("可视化键盘")
        group.setObjectName("visualKeyboardGroup")
        group.setMinimumWidth(900)
        keyboard_layout = QHBoxLayout(group)
        keyboard_layout.setContentsMargins(18, 20, 18, 16)
        keyboard_layout.setSpacing(22)

        main_keys = QVBoxLayout()
        main_keys.setSpacing(6)
        for row in KEYBOARD_ROWS:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(6)
            row_layout.setAlignment(Qt.AlignCenter)
            for key in row:
                width = 280 if key == "space" else (72 if key in ("esc", "shift", "ctrl", "alt") else 46)
                row_layout.addWidget(self._create_key_button(key, width))
            main_keys.addLayout(row_layout)
        keyboard_layout.addLayout(main_keys, 1)

        nav_grid = QGridLayout()
        nav_grid.setSpacing(8)
        for row, values in enumerate(NAVIGATION_KEYS):
            for column, key in enumerate(values):
                if key is not None:
                    nav_grid.addWidget(self._create_key_button(key, 56), row, column)
        keyboard_layout.addLayout(nav_grid)
        return group

    def _create_key_button(self, key, width):
        button = QPushButton(KEY_DISPLAY.get(key, key))
        button.setProperty("keyboardKey", True)
        button.setFixedWidth(width)
        button.setFixedHeight(44)
        button.clicked.connect(lambda checked=False, value=key: self._on_key_clicked(value))
        self.key_buttons[key] = button
        return button

    def _build_footer(self):
        layout = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.setObjectName("dialogPrimaryButton")
        save_button.clicked.connect(self._save)
        reset_button = QPushButton("重置")
        reset_button.setObjectName("dialogResetButton")
        reset_button.clicked.connect(self._reset)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        layout.addStretch(1)
        layout.addWidget(reset_button)
        layout.addWidget(close_button)
        layout.addWidget(save_button)
        return layout

    def _refresh_professions(self, selected_name=""):
        self.profession_combo.blockSignals(True)
        self.profession_combo.clear()
        self.profession_combo.addItems(self.store.names())
        if selected_name:
            index = self.profession_combo.findText(selected_name)
            if index >= 0:
                self.profession_combo.setCurrentIndex(index)
        self.profession_combo.blockSignals(False)
        self._on_profession_changed(self.profession_combo.currentText())

    def _current_profile(self):
        return self.store.get(self.profession_combo.currentText())

    def _set_enabled_state(self):
        enabled = self._current_profile() is not None
        self.delete_button.setEnabled(enabled)
        self.attack_type_combo.setEnabled(enabled)
        if hasattr(self, "jump_attack_checkbox"):
            self.jump_attack_checkbox.setEnabled(enabled)
        for button in self.function_buttons.values():
            button.setEnabled(enabled)
        if self.add_buff_button is not None:
            self.add_buff_button.setEnabled(enabled)
        for button in self.key_buttons.values():
            button.setEnabled(enabled)

    def _on_profession_changed(self, name):
        self.selected_key = None
        self.pending_function = None
        if name:
            self.store.select(name)
        profile = self._current_profile()
        if profile:
            attack_type = profile.get("main_attack_type", "directional")
            index = self.attack_type_combo.findData(attack_type)
            self.attack_type_combo.blockSignals(True)
            self.attack_type_combo.setCurrentIndex(max(index, 0))
            self.attack_type_combo.blockSignals(False)
            if hasattr(self, "jump_attack_checkbox"):
                self.jump_attack_checkbox.blockSignals(True)
                self.jump_attack_checkbox.setChecked(bool(profile.get("jump_attack", False)))
                self.jump_attack_checkbox.blockSignals(False)
        elif hasattr(self, "jump_attack_checkbox"):
            self.jump_attack_checkbox.blockSignals(True)
            self.jump_attack_checkbox.setChecked(False)
            self.jump_attack_checkbox.blockSignals(False)
        self.current_function_label.setText("当前按键功能：无")
        self.interval_container.setVisible(False)
        self.extra_buff_ids = []
        self.extra_buff_ids = list(self._ordered_extra_buff_ids())
        self._rebuild_function_chips()
        self._set_enabled_state()
        self._refresh_keyboard()

    def _on_attack_type_changed(self):
        profile = self._current_profile()
        if profile:
            profile["main_attack_type"] = self.attack_type_combo.currentData()

    def _on_jump_attack_changed(self, _state=None):
        profile = self._current_profile()
        if profile and hasattr(self, "jump_attack_checkbox"):
            profile["jump_attack"] = bool(self.jump_attack_checkbox.isChecked())

    def _on_key_clicked(self, key):
        self.selected_key = key
        if self.pending_function:
            function_id = self.pending_function
            self.pending_function = None
            if function_id == "clear":
                self._clear_selected_key()
            else:
                self._assign_selected_key(function_id)
            return

        function_id = self._function_for_key(key)
        label = self._function_meta(function_id).get("label", "无")
        self.current_function_label.setText(f"当前按键：{key}　当前按键功能：{label}")
        self._show_interval(function_id)
        self._refresh_keyboard()

    def _on_function_clicked(self, function_id):
        if self.selected_key:
            if function_id == "clear":
                self._clear_selected_key()
            else:
                self._assign_selected_key(function_id)
            return
        self.pending_function = function_id
        label = self._function_meta(function_id).get("label", function_id)
        self.current_function_label.setText(f"当前按键功能：{label}（请选择键盘按键）")
        self._show_interval(function_id)

    def _assign_selected_key(self, function_id):
        profile = self._current_profile()
        if not profile or not self.selected_key:
            return
        bindings = profile.setdefault("bindings", {})
        for bound_function, key in list(bindings.items()):
            if key == self.selected_key or bound_function == function_id:
                del bindings[bound_function]
        bindings[function_id] = self.selected_key
        label = self._function_meta(function_id).get("label", function_id)
        self.current_function_label.setText(
            f"当前按键：{self.selected_key}　当前按键功能：{label}"
        )
        self._show_interval(function_id)
        self._refresh_keyboard()

    def _clear_selected_key(self):
        profile = self._current_profile()
        if not profile or not self.selected_key:
            return
        bindings = profile.setdefault("bindings", {})
        for function_id, key in list(bindings.items()):
            if key == self.selected_key:
                del bindings[function_id]
        self.current_function_label.setText(
            f"当前按键：{self.selected_key}　当前按键功能：无"
        )
        self.interval_container.setVisible(False)
        self._refresh_keyboard()

    def _function_for_key(self, key):
        profile = self._current_profile()
        if not profile:
            return None
        for function_id, bound_key in profile.setdefault("bindings", {}).items():
            if bound_key == key:
                return function_id
        return None

    def _show_interval(self, function_id):
        definition = self._function_meta(function_id)
        show = bool(definition and definition.get("requires_interval"))
        self.interval_container.setVisible(show)
        if not show:
            return
        profile = self._current_profile()
        if not profile:
            return
        intervals = profile.setdefault("intervals", {})
        interval_settings = {
            "buff": (60, "BUFF间隔（秒）："),
            "pet_food": (600, "喂食间隔（秒）："),
            "experience_coupon": (3600, "经验券间隔（秒）："),
        }
        if function_id in interval_settings:
            default_value, label = interval_settings[function_id]
        elif extra_buff_meta(function_id):
            default_value, label = (
                60,
                f"{self._function_meta(function_id).get('label', 'BUFF')}间隔（秒）：",
            )
        else:
            default_value, label = (60, "触发间隔（秒）：")
        self.interval_label.setText(label)
        self.interval_spin.blockSignals(True)
        self.interval_spin.setValue(int(intervals.get(function_id, default_value)))
        self.interval_spin.setProperty("functionId", function_id)
        self.interval_spin.blockSignals(False)

    def _on_interval_changed(self, value):
        profile = self._current_profile()
        function_id = self.interval_spin.property("functionId")
        if profile and function_id:
            profile.setdefault("intervals", {})[function_id] = int(value)

    def _refresh_keyboard(self):
        profile = self._current_profile()
        bindings = profile.setdefault("bindings", {}) if profile else {}
        function_by_key = {key: function_id for function_id, key in bindings.items()}
        for key, button in self.key_buttons.items():
            function_id = function_by_key.get(key)
            meta = self._function_meta(function_id)
            color = meta.get("color", "#ffffff")
            text_color = readable_text_color(color) if function_id else "#334155"
            border = "3px solid #4f46e5" if key == self.selected_key else "1px solid #cbd6e3"
            hover_color = color if function_id else "#f0efff"
            function_label = meta.get("label", "未绑定")
            button.setToolTip(f"{KEY_DISPLAY.get(key, key)} · {function_label}")
            button.setStyleSheet(
                "QPushButton {"
                f"background-color: {color}; color: {text_color}; border: {border}; "
                "border-radius: 7px; padding: 0; font-weight: 700;"
                "}"
                "QPushButton:hover {"
                f"background-color: {hover_color}; border: 2px solid #8178dd;"
                "}"
                "QPushButton:disabled {"
                "background-color: #edf1f6; color: #a1adbd; border-color: #dce3ec;"
                "}"
            )

    def _add_profession(self):
        dialog = AddProfessionDialog(self.store.names(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        name, attack_type, bindings = dialog.values()
        if self.store.add(name, attack_type, bindings):
            self.store.save()
            self._refresh_professions(name)
            self.profiles_changed.emit()

    def _delete_profession(self):
        name = self.profession_combo.currentText()
        if not name:
            return
        result = QMessageBox.question(
            self,
            "删除职业",
            f"确定删除职业“{name}”及其全部键位配置吗？",
        )
        if result != QMessageBox.Yes:
            return
        self.store.delete(name)
        self.store.save()
        self._refresh_professions()
        self.profiles_changed.emit()

    def _reset(self):
        name = self.profession_combo.currentText()
        if not name:
            return
        result = QMessageBox.question(self, "重置配置", f"确定清空“{name}”的全部键位吗？")
        if result != QMessageBox.Yes:
            return
        self.store.reset(name)
        self.selected_key = None
        self.pending_function = None
        self._on_profession_changed(name)

    def _save(self):
        if self.profession_combo.currentText():
            self.store.select(self.profession_combo.currentText())
        self.store.save()
        self.profiles_changed.emit()
        QMessageBox.information(self, "保存配置", "职业键位配置已保存。")

    def closeEvent(self, event):
        self.store.save()
        self.profiles_changed.emit()
        event.accept()
