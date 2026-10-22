'''
UI main
'''
# Standard import
import sys
import os
import json
import copy
import logging
import datetime
import subprocess

import cv2

# PySide 6
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QCheckBox, QListWidget, QFileDialog, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QTabWidget, QGroupBox, QFormLayout,
    QSizePolicy, QComboBox, QListWidgetItem, QScrollArea, QMenu,
    QInputDialog, QMessageBox, QFrame, QGridLayout, QSplitter,
    QDialog, QDialogButtonBox,
    QTimeEdit, QSpinBox,
)
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QPixmap, QImage, QIcon
from PySide6.QtCore import QEvent, Qt, QTimer, Signal, QTime

# Local import
from src.utils.logger import logger
from src.utils.ui import (
    validate_numerical_input, clear_debug_canvas,
    create_error_label, ModernSpinBox, SingleKeyEdit, QtLogHandler,
    create_advance_setting_gbox,
)
from src.utils.paths import MEDIA, MINIMAPS
from src.utils.common import (
    load_yaml, override_cfg, is_mac, save_yaml, get_cfg_diff, load_yaml_with_comments
)
from src.utils.image_io import read_image, write_image
from src.utils.nametag import (
    DEFAULT_NAMETAG_DIR,
    crop_nametag_to_layers,
    delete_saved_nametag,
    list_saved_nametags,
    load_nametag_layers,
    nametag_image_path,
    normalize_nametag_layers,
    prepare_nametag_template,
    safe_nametag_name,
    save_nametag_boxes,
    save_nametag_layers,
)
from src.ui.nametag_picker import NametagPickerPopup
from src.utils.profession_bindings import reset_profession_overrides
from src.utils.global_var import WINDOW_WORKING_SIZE
from src.ui.profession_config import ProfessionConfigStore, KeyboardConfigDialog
from src.ui.resource_tabs import (
    MapManagementTab,
    MonsterManagementTab,
    RecordTab,
    ResourceRepository,
)

# window size for each tab
if is_mac():
    TAB_WINDOW_SIZE = {
        '首页': (700, 850),
        '地图': (900, 800),
        '怪物': (900, 800),
        '录制': (900, 800),
        '运行日志': (900, 800),
        '运行监控': (1050, 720),
        '定时关机': (560, 420),
        '高级设置': (750, 800),
        '路线地图': (400, 400),
    }
else:
    TAB_WINDOW_SIZE = {
        '首页': (700, 850),
        '地图': (920, 820),
        '怪物': (920, 820),
        '录制': (920, 820),
        '运行日志': (900, 800),
        '运行监控': (1050, 720),
        '定时关机': (560, 420),
        '高级设置': (720, 800),
        '路线地图': (720, 720),
    }

ADV_SETTINGS_HIDE = [
    'key', 'bot', 'profession',
    'rune_warning_cn', 'rune_warning_eng',
    'rune_enable_msg_cn', 'rune_enable_msg_eng',
    'rune_detect', 'rune_find', 'rune_solver',
] # cfg tile here will not shown in advanced settings tabs


DEFAULT_POTION_PROFILE = {
    "enable": False,
    "add_hp_percent_min": 35,
    "add_hp_percent_max": 70,
    "add_hp_potion_amount": 300,  # absolute HP restored per press
    "add_hp_max": 0,              # character max HP (0 = single-press fallback)
    "add_mp_percent_min": 20,
    "add_mp_percent_max": 60,
    "add_mp_potion_amount": 150,  # absolute MP restored per press
    "add_mp_max": 0,              # character max MP (0 = single-press fallback)
    "add_hp_max_presses": 5,
    "add_mp_max_presses": 5,
    "add_hp_press_interval": 0.15,
    "add_mp_press_interval": 0.15,
}


class PotionConfigDialog(QDialog):
    """Small dialog for dual-mode potion healing profile."""

    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("药品配置")
        self.setModal(True)
        self.setMinimumWidth(480)

        data = dict(DEFAULT_POTION_PROFILE)
        if isinstance(profile, dict):
            data.update(profile)
        self._source_profile = dict(data)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(14)

        title = QLabel("药品补充配置")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #263449;")
        layout.addWidget(title)

        hint = QLabel(
            "启用后：当当前值 ≤ 下限时触发，按药品绝对回复量多次按键补到上限。"
            "需填写角色最大HP/MP；未填或为0时回退为单次按键。"
            "未启用时继续使用主页单一阈值。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #718096;")
        layout.addWidget(hint)

        self.enable_checkbox = QCheckBox("启用药品配置")
        self.enable_checkbox.setChecked(bool(data.get("enable", False)))
        layout.addWidget(self.enable_checkbox)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.hp_char_max = ModernSpinBox()
        self.hp_char_max.setRange(0, 999999)
        self.hp_char_max.setValue(int(data.get("add_hp_max", 0) or 0))
        self.mp_char_max = ModernSpinBox()
        self.mp_char_max.setRange(0, 999999)
        self.mp_char_max.setValue(int(data.get("add_mp_max", 0) or 0))
        form.addRow("角色最大HP:", self.hp_char_max)
        form.addRow("角色最大MP:", self.mp_char_max)

        self.hp_min = ModernSpinBox()
        self.hp_min.setRange(0, 100)
        self.hp_min.setSuffix(" %")
        self.hp_min.setValue(int(data.get("add_hp_percent_min", 35)))
        self.hp_max = ModernSpinBox()
        self.hp_max.setRange(0, 100)
        self.hp_max.setSuffix(" %")
        self.hp_max.setValue(int(data.get("add_hp_percent_max", 70)))
        self.hp_amount = ModernSpinBox()
        self.hp_amount.setRange(1, 99999)
        self.hp_amount.setValue(int(data.get("add_hp_potion_amount", 300)))

        hp_range_row = QHBoxLayout()
        hp_range_row.setSpacing(6)
        hp_range_row.addWidget(self.hp_min)
        hp_range_row.addWidget(QLabel("-"))
        hp_range_row.addWidget(self.hp_max)
        form.addRow("HP补充阈值:", hp_range_row)
        form.addRow("HP药品量(如100/300):", self.hp_amount)

        self.mp_min = ModernSpinBox()
        self.mp_min.setRange(0, 100)
        self.mp_min.setSuffix(" %")
        self.mp_min.setValue(int(data.get("add_mp_percent_min", 20)))
        self.mp_max = ModernSpinBox()
        self.mp_max.setRange(0, 100)
        self.mp_max.setSuffix(" %")
        self.mp_max.setValue(int(data.get("add_mp_percent_max", 60)))
        self.mp_amount = ModernSpinBox()
        self.mp_amount.setRange(1, 99999)
        self.mp_amount.setValue(int(data.get("add_mp_potion_amount", 150)))

        mp_range_row = QHBoxLayout()
        mp_range_row.setSpacing(6)
        mp_range_row.addWidget(self.mp_min)
        mp_range_row.addWidget(QLabel("-"))
        mp_range_row.addWidget(self.mp_max)
        form.addRow("MP补充阈值:", mp_range_row)
        form.addRow("MP药品量(如100/150):", self.mp_amount)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Ok).setObjectName("dialogPrimaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        if self.hp_min.value() > self.hp_max.value():
            QMessageBox.warning(self, "药品配置", "HP 下限不能大于上限。")
            return
        if self.mp_min.value() > self.mp_max.value():
            QMessageBox.warning(self, "药品配置", "MP 下限不能大于上限。")
            return
        self.accept()

    def get_profile(self):
        profile = dict(DEFAULT_POTION_PROFILE)
        # Preserve max_presses / press_interval from existing config if present
        for key in (
            "add_hp_max_presses", "add_mp_max_presses",
            "add_hp_press_interval", "add_mp_press_interval",
            "max_presses", "press_interval",
        ):
            if key in self._source_profile:
                profile[key] = self._source_profile[key]
        profile.update({
            "enable": self.enable_checkbox.isChecked(),
            "add_hp_percent_min": self.hp_min.value(),
            "add_hp_percent_max": self.hp_max.value(),
            "add_hp_potion_amount": self.hp_amount.value(),
            "add_hp_max": self.hp_char_max.value(),
            "add_mp_percent_min": self.mp_min.value(),
            "add_mp_percent_max": self.mp_max.value(),
            "add_mp_potion_amount": self.mp_amount.value(),
            "add_mp_max": self.mp_char_max.value(),
        })
        return profile



class MainWindow(QMainWindow):
    '''
    MainWindow
    '''
    request_close = Signal()

    def __init__(self, controller=None):
        super().__init__()

        # UI window Icon
        self.setWindowIcon(QIcon(os.path.join(MEDIA, "icon.png")))

        self.controller = controller # autoBotController
        self.prev_tab_window_size = None
        #
        self.selected_map = ""

        # Load default yaml and platform yaml as base config
        _, self.comments, self.comments_section = load_yaml_with_comments("config/config_default.yaml")
        self.cfg_base = load_yaml("config/config_default.yaml")
        if is_mac():
            self.cfg_base = override_cfg(self.cfg_base,
                                         load_yaml("config/config_macOS.yaml"))
        self.cfg_fallback = copy.deepcopy(self.cfg_base)
        self.cfg = copy.deepcopy(self.cfg_fallback)
        self.path_cfg_custom = "config/config_custom.yaml" # Custom config path
        self.profession_store = ProfessionConfigStore()
        self.resource_repository = ResourceRepository()
        # Prefer assets/nametag (same as engine). Migrate legacy ./nametag imports.
        self.nametag_dir = DEFAULT_NAMETAG_DIR
        try:
            import shutil
            legacy = os.path.join(os.getcwd(), "nametag")
            target = self.nametag_dir
            if os.path.isdir(legacy) and os.path.abspath(legacy) != os.path.abspath(target):
                os.makedirs(target, exist_ok=True)
                for name in os.listdir(legacy):
                    src = os.path.join(legacy, name)
                    dst = os.path.join(target, name)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        logger.info(f"[UI] Migrated nametag file to assets: {name}")
        except Exception as err:
            logger.warning(f"[UI] Nametag legacy migrate skipped: {err}")
        self.nametag_picker = None

        # Load database
        self.data = self.resource_repository.data

        # Window Settings
        self.setWindowTitle("MapleStory AutoLevelUp")
        self.setMinimumSize(1, 1)
        self.resize(TAB_WINDOW_SIZE['首页'][0],
                    TAB_WINDOW_SIZE['首页'][1])

        # Setup tabs
        self.tabs = QTabWidget()
        self.tab_main = self.setup_main_tab()
        # Set up logging before the resource tabs so their startup messages are captured.
        self.tab_log = self.setup_log_tab()
        self.tab_map = self.setup_map_tab()
        self.tab_monster = self.setup_monster_tab()
        self.tab_record = self.setup_record_tab()
        self.tab_advance_setting = self.setup_advance_setting_tab()
        self.tab_route_map_viz = self.setup_route_map_viz_tab()
        self.tab_game_window_viz = self.setup_game_window_viz_tab()
        self.tab_shutdown_monitor = self.setup_shutdown_monitor_tab()
        self.tab_shutdown_monitor.setParent(self)
        self.tab_shutdown_monitor.hide()

        # Add tabs to tab widget
        self.tabs.addTab(self.tab_main, "首页")
        self.tabs.addTab(self.tab_map, "地图")
        self.tabs.addTab(self.tab_monster, "怪物")
        self.tabs.addTab(self.tab_record, "录制")
        self.tabs.addTab(self.tab_log, "运行日志")
        self.tabs.addTab(self.tab_game_window_viz, "运行监控")

        # Change tabs signals
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Put tab widget to layout
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addLayout(self.create_home_footer())
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.apply_modern_style()

        # Load previous stored UI state
        self.load_ui_state()
        self.apply_config_to_ui()
        self._start_shutdown_monitor_timer()

        # Signal
        self.request_close.connect(self.close)

    def setup_main_tab(self):
        '''
        Init the compact home page from the profession-driven workflow.
        '''
        scroll_area = QScrollArea()
        self.home_scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(14, 14, 14, 14)
        scroll_layout.setSpacing(14)

        header = QLabel("MapleStory AutoLevelUp\n视觉识别 · 职业配置 · 自动练级")
        header.setObjectName("homeHero")
        header.setAlignment(Qt.AlignCenter)
        header.setMinimumHeight(116)
        scroll_layout.addWidget(header)

        self.profession_gbox = self.create_profession_gbox()
        scroll_layout.addWidget(self.profession_gbox)

        self.function_gbox = self.create_home_function_gbox()
        scroll_layout.addWidget(self.function_gbox)

        scroll_layout.addStretch(1)

        scroll_area.setWidget(scroll_widget)

        tab_main = QWidget()
        layout = QVBoxLayout(tab_main)
        layout.addWidget(scroll_area)

        return tab_main

    def setup_log_tab(self):
        """Create a dedicated log view that expands with the application window."""
        tab_log = QWidget()
        layout = QVBoxLayout(tab_log)
        layout.setContentsMargins(14, 14, 14, 14)

        self.log_gbox = self.create_log_gbox()
        self.log_gbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.log_gbox, 1)

        return tab_log

    def setup_map_tab(self):
        self.map_management_tab = MapManagementTab(
            self.resource_repository,
            config_path_provider=self.prepare_route_recorder_config,
            bot_running_provider=lambda: self.button_start_pause.isChecked(),
            stop_bot_callback=self._stop_bot_for_recording,
        )
        self.map_management_tab.map_selected.connect(self.on_managed_map_selected)
        self.map_management_tab.record_requested.connect(self.open_recording_for_map)
        self.map_management_tab.resources_changed.connect(self.on_resources_changed)
        self.map_management_tab.recording_state_changed.connect(
            self.on_route_recording_state_changed
        )
        self.selected_map = self.map_management_tab.current_map
        return self.map_management_tab

    def _stop_bot_for_recording(self):
        """Stop running bot so rope/route recorders can own input."""
        if self.button_start_pause.isChecked():
            self.button_start_pause.setChecked(False)
            self.toggle_start_ui()

    def setup_monster_tab(self):
        self.monster_management_tab = MonsterManagementTab(self.resource_repository)
        self.monster_management_tab.resources_changed.connect(self.on_resources_changed)
        return self.monster_management_tab

    def setup_record_tab(self):
        self.record_tab = RecordTab(
            self.resource_repository,
            config_path_provider=self.prepare_route_recorder_config,
        )
        self.record_tab.recording_state_changed.connect(self.on_route_recording_state_changed)
        self.record_tab.recording_finished.connect(self.on_route_recording_finished)
        self.record_tab.set_current_map(self.selected_map)
        return self.record_tab

    def prepare_route_recorder_config(self):
        self.update_cfg_from_main_ui()
        config_path = "config/.config_tmp.yaml"
        save_yaml(self.cfg, config_path)
        return config_path

    def create_profession_gbox(self):
        gbox = QGroupBox("职业选择")
        layout = QHBoxLayout(gbox)
        layout.setSpacing(12)

        self.profession_combo = QComboBox()
        self.profession_combo.setMinimumWidth(180)
        self.profession_combo.currentTextChanged.connect(self.on_profession_selected)
        layout.addWidget(self.profession_combo)

        layout.addWidget(QLabel("窗口名："))
        self.window_title_edit = QLineEdit(self.cfg["game_window"]["title"])
        self.window_title_edit.setPlaceholderText("请输入游戏窗口标题")
        layout.addWidget(self.window_title_edit, 1)

        self.refresh_profession_selector()
        return gbox

    def create_home_function_gbox(self):
        gbox = QGroupBox("功能设置")
        layout = QVBoxLayout(gbox)
        layout.setContentsMargins(18, 22, 18, 16)
        layout.setSpacing(12)

        def create_setting_row(title):
            row = QFrame()
            row.setObjectName("settingRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            row_layout.setSpacing(16)
            title_label = QLabel(title)
            title_label.setObjectName("settingRowTitle")
            title_label.setFixedWidth(82)
            title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_layout.addWidget(title_label)
            return row, row_layout

        def create_field(caption, widget):
            field = QWidget()
            field_layout = QVBoxLayout(field)
            field_layout.setContentsMargins(0, 0, 0, 0)
            field_layout.setSpacing(5)
            caption_label = QLabel(caption)
            caption_label.setObjectName("settingFieldCaption")
            caption_label.setWordWrap(True)
            field_layout.addWidget(caption_label)
            field_layout.addWidget(widget)
            return field

        nametag_card, nametag_card_layout = create_setting_row("角色识别")
        nametag_content = QVBoxLayout()
        nametag_content.setSpacing(6)
        nametag_caption = QLabel("角色名图片（截脚下青色名牌，或直接导入游戏截图）")
        nametag_caption.setObjectName("settingFieldCaption")
        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        self.character_name_edit = QLineEdit()
        self.character_name_edit.setMinimumWidth(180)
        self.character_name_edit.setReadOnly(True)
        self.character_name_edit.setPlaceholderText("尚未导入，点击名片夹可选择历史角色")
        self.character_name_edit.setToolTip("当前使用的角色名图片，点击打开名片夹")
        self.character_name_edit.installEventFilter(self)
        self.button_nametag_picker = QPushButton("名片夹")
        self.button_nametag_picker.setMinimumWidth(84)
        self.button_nametag_picker.setToolTip("选择或删除历史导入的角色名图片")
        self.button_nametag_picker.clicked.connect(self.toggle_nametag_picker)
        self.button_import_nametag = QPushButton("导入图片")
        self.button_import_nametag.setObjectName("secondaryActionButton")
        self.button_import_nametag.setMinimumWidth(104)
        self.button_import_nametag.clicked.connect(self.import_character_name_image)
        image_row.addWidget(self.character_name_edit, 1)
        image_row.addWidget(self.button_nametag_picker)
        image_row.addWidget(self.button_import_nametag)
        nametag_content.addWidget(nametag_caption)
        nametag_content.addLayout(image_row)
        nametag_card_layout.addLayout(nametag_content, 1)
        layout.addWidget(nametag_card)

        health_card, health_row = create_setting_row("生命管理")
        self.home_hp_percent = ModernSpinBox()
        self.home_hp_percent.setRange(0, 100)
        self.home_hp_percent.setSuffix(" %")
        self.home_hp_percent.setMinimumWidth(126)
        self.home_mp_percent = ModernSpinBox()
        self.home_mp_percent.setRange(0, 100)
        self.home_mp_percent.setSuffix(" %")
        self.home_mp_percent.setMinimumWidth(126)
        health_row.addWidget(create_field("HP 补充阈值", self.home_hp_percent), 1)
        health_row.addWidget(create_field("MP 补充阈值", self.home_mp_percent), 1)
        self.button_potion_config = QPushButton("药品配置")
        self.button_potion_config.setObjectName("secondaryActionButton")
        self.button_potion_config.setMinimumWidth(96)
        self.button_potion_config.setToolTip("配置区间补药、绝对药品量与角色最大HP/MP（可选）")
        self.button_potion_config.clicked.connect(self.open_potion_config_dialog)
        health_row.addWidget(self.button_potion_config)
        health_row.addStretch(1)
        layout.addWidget(health_card)

        attack_card, attack_row = create_setting_row("攻击参数")
        self.home_attack_range_x = ModernSpinBox()
        self.home_attack_range_x.setRange(0, WINDOW_WORKING_SIZE[0])
        self.home_attack_range_x.setMinimumWidth(96)
        self.home_attack_range_y = ModernSpinBox()
        self.home_attack_range_y.setRange(0, WINDOW_WORKING_SIZE[1])
        self.home_attack_range_y.setMinimumWidth(96)
        self.home_attack_cooldown = ModernSpinBox()
        self.home_attack_cooldown.setRange(0, 9999)
        self.home_attack_cooldown.setSuffix(" ×0.1秒")
        self.home_attack_cooldown.setMinimumWidth(118)
        self.home_aoe_trigger_count = ModernSpinBox()
        self.home_aoe_trigger_count.setRange(2, 20)
        self.home_aoe_trigger_count.setMinimumWidth(96)
        self.home_aoe_cooldown = ModernSpinBox()
        self.home_aoe_cooldown.setRange(0, 9999)
        self.home_aoe_cooldown.setSuffix(" ×0.1秒")
        self.home_aoe_cooldown.setMinimumWidth(118)

        attack_content = QWidget()
        self.home_attack_grid = QGridLayout(attack_content)
        self.home_attack_grid.setContentsMargins(0, 0, 0, 0)
        self.home_attack_grid.setHorizontalSpacing(14)
        self.home_attack_grid.setVerticalSpacing(10)
        self.home_attack_range_x_field = create_field(
            "水平范围", self.home_attack_range_x
        )
        self.home_attack_range_y_field = create_field(
            "垂直范围", self.home_attack_range_y
        )
        self.home_attack_cooldown_field = create_field(
            "攻击冷却", self.home_attack_cooldown
        )
        self.home_aoe_trigger_count_field = create_field(
            "群攻怪物数", self.home_aoe_trigger_count
        )
        self.home_aoe_cooldown_field = create_field(
            "群攻冷却", self.home_aoe_cooldown
        )
        self.home_attack_grid.addWidget(self.home_attack_range_x_field, 0, 0)
        self.home_attack_grid.addWidget(self.home_attack_range_y_field, 0, 1)
        self.home_attack_grid.addWidget(self.home_attack_cooldown_field, 0, 2)
        self.home_attack_grid.addWidget(self.home_aoe_trigger_count_field, 1, 0)
        self.home_attack_grid.addWidget(self.home_aoe_cooldown_field, 1, 1)
        for column in range(3):
            self.home_attack_grid.setColumnStretch(column, 1)
        attack_row.addWidget(attack_content, 1)
        layout.addWidget(attack_card)

        mode_card, mode_row = create_setting_row("运行模式")
        self.bot_mode = QComboBox()
        self.bot_mode.addItem("普通路线", "normal")
        self.bot_mode.addItem("辅助模式", "aux")
        self.bot_mode.addItem("巡逻模式", "patrol")
        self.bot_mode.addItem("智能巡逻", "smart_patrol")
        self.bot_mode.setMinimumWidth(220)
        self.bot_mode.currentIndexChanged.connect(self.on_bot_mode_changed)
        mode_row.addWidget(create_field("执行方式", self.bot_mode), 1)
        mode_row.addStretch(1)
        layout.addWidget(mode_card)

        return gbox

    def create_home_footer(self):
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.button_settings = QPushButton("设置")
        self.button_settings.setObjectName("settingsButton")
        self.button_settings.setFixedSize(78, 48)
        settings_menu = QMenu(self.button_settings)
        keyboard_action = settings_menu.addAction("键盘设置")
        keyboard_action.triggered.connect(self.open_keyboard_config)
        shutdown_action = settings_menu.addAction("定时关机")
        shutdown_action.triggered.connect(self.open_shutdown_monitor)
        load_action = settings_menu.addAction("加载 YAML 配置")
        self.load_config_error_label = create_error_label()
        load_action.triggered.connect(
            lambda: self.load_config(self.load_config_error_label)
        )
        save_action = settings_menu.addAction("保存当前配置")
        save_action.triggered.connect(self.save_current_config)
        self.button_settings.setMenu(settings_menu)

        self.button_start_pause = QPushButton("开始")
        self.button_start_pause.setObjectName("primaryActionButton")
        self.button_start_pause.setCheckable(True)
        self.button_start_pause.setMinimumSize(150, 48)
        self.button_start_pause.clicked.connect(self.toggle_start_ui)

        self.button_screenshot = QPushButton("截图 F2")
        self.button_screenshot.clicked.connect(self.toggle_screenshot_ui)
        self.button_screenshot.setVisible(False)
        self.button_record = QPushButton("录制 F3")
        self.button_record.setCheckable(True)
        self.button_record.clicked.connect(self.toggle_record_ui)
        self.button_record.setVisible(False)

        help_button = QPushButton("帮助")
        help_button.setObjectName("helpActionButton")
        help_button.clicked.connect(self.show_home_help)

        layout.addWidget(self.button_settings)
        layout.addWidget(self.button_start_pause)
        layout.addStretch(1)
        layout.addWidget(help_button)
        return layout

    def refresh_profession_selector(self):
        if not hasattr(self, "profession_combo"):
            return
        selected_name = self.profession_store.selected_name()
        self.profession_combo.blockSignals(True)
        self.profession_combo.clear()
        self.profession_combo.addItem("请先添加职业", "")
        for name in self.profession_store.names():
            self.profession_combo.addItem(name, name)
        if selected_name:
            index = self.profession_combo.findData(selected_name)
            if index >= 0:
                self.profession_combo.setCurrentIndex(index)
        self.profession_combo.blockSignals(False)
        self.on_profession_selected()

    def on_profession_selected(self, _text=None):
        name = self.profession_combo.currentData() or ""
        self.profession_store.select(name)
        self.profession_store.apply_to_cfg(self.cfg, name, self.cfg_fallback)
        if name:
            self.statusBar().showMessage(f"状态：已选择职业“{name}”")
        else:
            self.statusBar().showMessage("状态：就绪 - 请通过左下角设置添加职业")
        self._sync_home_attack_fields_from_cfg()

    def open_keyboard_config(self):
        selected_name = self.profession_combo.currentData() or ""
        dialog = KeyboardConfigDialog(self.profession_store, selected_name, self)
        dialog.profiles_changed.connect(self.refresh_profession_selector)
        dialog.exec()
        self.refresh_profession_selector()

    def open_shutdown_monitor(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("定时关机")
        dialog.setModal(True)
        dialog.resize(*TAB_WINDOW_SIZE.get("定时关机", (560, 420)))
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        self.tab_shutdown_monitor.setParent(dialog)
        self.tab_shutdown_monitor.show()
        layout.addWidget(self.tab_shutdown_monitor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()
        self.tab_shutdown_monitor.setParent(self)
        self.tab_shutdown_monitor.hide()
        self._collect_shutdown_monitor_from_ui()

    def import_character_name_image(self):
        image_name, accepted = QInputDialog.getText(
            self,
            "导入角色名图片",
            "请输入角色名图片名称：",
        )
        image_name = (image_name or "").strip()
        if not accepted or not image_name:
            return

        # Explicit 一层 / 两层 / 三层 choice at import (not buried in config only).
        layer_label, layer_ok = QInputDialog.getItem(
            self,
            "选择名片层数",
            "挂机名片匹配层数（可从三层截图裁成一层/两层）：\n"
            "一层 = 仅角色名\n"
            "两层 = 角色名 + 公会或勋章\n"
            "三层 = 角色名 + 公会 + 勋章（硬匹配两行副带）\n"
            "日丁+比比拉布+勋章建议选「三层」。",
            ["一层（仅名字）", "两层（名+公会/勋章）", "三层（名+公会+勋章）"],
            2,
            False,
        )
        if not layer_ok:
            return
        layers = {
            "一层（仅名字）": 1,
            "两层（名+公会/勋章）": 2,
            "三层（名+公会+勋章）": 3,
        }.get(layer_label, 3)

        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择角色名截图",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)",
        )
        if not source_path:
            return

        source_image = read_image(source_path, cv2.IMREAD_UNCHANGED)
        if source_image is None:
            QMessageBox.warning(self, "导入失败", "无法读取所选图片，请重新选择。")
            return

        try:
            safe_name = safe_nametag_name(image_name)
        except ValueError as error:
            QMessageBox.warning(self, "导入失败", str(error))
            return

        os.makedirs(self.nametag_dir, exist_ok=True)
        target_path = nametag_image_path(safe_name, self.nametag_dir)
        if os.path.exists(target_path):
            overwrite = QMessageBox.question(
                self,
                "覆盖图片",
                f"角色名图片“{safe_name}”已经存在，是否覆盖？",
            )
            if overwrite != QMessageBox.Yes:
                return

        prepared = prepare_nametag_template(source_image, layers=layers)
        prepared = crop_nametag_to_layers(prepared, layers)
        if not write_image(target_path, prepared):
            QMessageBox.warning(self, "导入失败", "图片保存失败，请检查目录权限。")
            return

        save_nametag_layers(safe_name, layers, self.nametag_dir)
        # Auto-measure name/guild/medal boxes once at import (<name>.boxes.json).
        try:
            boxes_path, boxes = save_nametag_boxes(
                safe_name, prepared, layers, self.nametag_dir
            )
            if boxes:
                logger.info(
                    f"[UI] Nametag boxes: {boxes_path} name={boxes.get('name')} "
                    f"guild={boxes.get('guild')} medal={boxes.get('medal')} "
                    f"second={boxes.get('second_kind')} source={boxes.get('source_scale')}"
                )
        except Exception as error:
            logger.warning(f"[UI] Nametag boxes not saved: {error}")
        self.cfg.setdefault("nametag", {})["layers"] = int(layers)
        self.cfg["nametag"]["name"] = safe_name
        self.apply_character_nametag(safe_name)
        logger.info(
            f"[UI] Imported character nametag: {target_path} layers={layers}"
        )
        self.statusBar().showMessage(
            f"状态：已导入角色名图片“{safe_name}”（{layer_label}）"
        )


    def eventFilter(self, watched, event):
        if (
            watched is getattr(self, "character_name_edit", None)
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.LeftButton
        ):
            self.toggle_nametag_picker()
            return True
        return super().eventFilter(watched, event)

    def _ensure_nametag_picker(self):
        if self.nametag_picker is None:
            self.nametag_picker = NametagPickerPopup(self)
            self.nametag_picker.nametag_selected.connect(self.apply_character_nametag)
            self.nametag_picker.nametag_deleted.connect(self.delete_character_nametag)
            self.nametag_picker.closed.connect(self._on_nametag_picker_closed)
        return self.nametag_picker

    def _on_nametag_picker_closed(self):
        self._ignore_nametag_picker_toggle = True
        QTimer.singleShot(0, self._clear_nametag_picker_toggle_guard)

    def _clear_nametag_picker_toggle_guard(self):
        self._ignore_nametag_picker_toggle = False

    def toggle_nametag_picker(self):
        if getattr(self, "_ignore_nametag_picker_toggle", False):
            return
        picker = self._ensure_nametag_picker()
        if picker.isVisible():
            picker.close()
            return
        self._show_nametag_picker()

    def _show_nametag_picker(self):
        picker = self._ensure_nametag_picker()
        current_name = self.cfg.get("nametag", {}).get("name", "")
        picker.populate(list_saved_nametags(self.nametag_dir), current_name)
        picker.show_below(self.character_name_edit)

    def apply_character_nametag(self, name, quiet=False):
        # QUIET_NAMETAG_AUTO_BIND_V1
        try:
            safe_name = safe_nametag_name(name)
        except ValueError as error:
            if not quiet:
                QMessageBox.warning(self, "选择失败", str(error))
            else:
                logger.warning(f"[UI] Invalid nametag name on auto-bind: {error}")
            return False

        image_path = nametag_image_path(safe_name, self.nametag_dir)
        if not os.path.isfile(image_path):
            # Keep the configured name in the field; only popup on manual pick.
            self.cfg.setdefault("nametag", {})["name"] = safe_name
            if hasattr(self, "character_name_edit"):
                self.character_name_edit.setText(safe_name)
            msg = f"找不到角色名图片“{safe_name}”（路径：{image_path}）"
            if quiet:
                logger.warning(f"[UI] {msg}")
                if hasattr(self, "statusBar"):
                    self.statusBar().showMessage(f"状态：{msg}", 5000)
            else:
                QMessageBox.warning(self, "选择失败", f"找不到角色名图片“{safe_name}”。")
            return False

        self.cfg.setdefault("nametag", {})["name"] = safe_name
        saved_layers = load_nametag_layers(safe_name, self.nametag_dir, default=None)
        if saved_layers is not None:
            self.cfg.setdefault("nametag", {})["layers"] = int(saved_layers)

        self.cfg["nametag"]["enable"] = True
        self.cfg.setdefault("player_detect", {})["mode"] = "auto"
        self.character_name_edit.setText(safe_name)
        logger.info(f"[UI] Selected character nametag image: {image_path}")
        self.statusBar().showMessage(f"状态：已选择角色名图片“{safe_name}”")
        return True

    def clear_character_nametag(self):
        self.cfg.setdefault("nametag", {})["name"] = ""
        self.cfg["nametag"]["enable"] = False
        self.character_name_edit.setText("")
        self.statusBar().showMessage("状态：已清除角色名图片")

    def delete_character_nametag(self, name):
        try:
            removed_path = delete_saved_nametag(name, self.nametag_dir)
        except (FileNotFoundError, ValueError) as error:
            QMessageBox.warning(self, "删除失败", str(error))
            return False

        logger.info(f"[UI] Deleted character nametag image: {removed_path}")
        current_name = self.cfg.get("nametag", {}).get("name", "")
        if current_name == name:
            self.clear_character_nametag()
        else:
            self.statusBar().showMessage(f"状态：已删除角色名图片“{name}”")

        picker = self.nametag_picker
        if picker is not None and picker.isVisible():
            picker.populate(
                list_saved_nametags(self.nametag_dir),
                self.cfg.get("nametag", {}).get("name", ""),
            )
        return True

    def show_home_help(self):
        QMessageBox.information(
            self,
            "首页使用说明",
            "1. 点击左下角绿色设置按钮，进入键盘设置。\n"
            "2. 添加职业并配置主攻、跳跃、位移、补血补蓝等按键。\n"
            "3. 输入游戏窗口标题并选择地图。\n"
            "4. 导入角色名图片后，可用名片夹快速切换历史角色，右侧 × 可删除。\n"
            "5. 按开始或 F1 启动，F2 截图，F3 录制。",
        )

    def _sync_home_attack_fields_from_cfg(self):
        if not hasattr(self, "home_attack_range_x"):
            return
        attack_type = self.cfg["bot"].get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        attack_cfg = self.cfg[section_name]
        self.home_attack_range_x.setValue(int(attack_cfg.get("range_x", 0)))
        self.home_attack_range_y.setValue(int(attack_cfg.get("range_y", 0)))
        cooldown = float(attack_cfg.get("cooldown", 0))
        self.home_attack_cooldown.setValue(round(cooldown * 10))
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        self.home_aoe_trigger_count.setValue(
            int(hybrid_cfg.get("aoe_trigger_count", 2))
        )
        self.home_aoe_cooldown.setValue(
            round(float(hybrid_cfg.get("aoe_cooldown", 0.9)) * 10)
        )

    def apply_modern_style(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #eef2f7;
            }
            QDialog, QMessageBox, QInputDialog, QFileDialog {
                color: #1f2937;
                background-color: #eef2f7;
            }
            QWidget {
                color: #1f2937;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #dce3ec;
                border-radius: 14px;
                background-color: #f7f9fc;
                top: -2px;
            }
            QTabBar::tab {
                background: transparent;
                color: #64748b;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 11px 14px;
                margin-right: 2px;
                min-width: 72px;
                min-height: 25px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #3730a3;
                border-bottom: 3px solid #4f46e5;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                color: #4338ca;
                background: #eef2ff;
            }
            QLabel#homeHero {
                color: white;
                font-size: 20px;
                font-weight: 700;
                border-radius: 16px;
                padding: 18px;
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #172554, stop: 0.52 #3730a3, stop: 1 #2563eb
                );
            }
            QLabel#sectionTitle {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QFrame#settingRow {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 11px;
            }
            QFrame#settingRow:hover {
                background-color: #f6f8ff;
                border-color: #c7d2fe;
            }
            QLabel#settingRowTitle {
                color: #1e293b;
                font-size: 13px;
                font-weight: 700;
                border: none;
                background-color: transparent;
            }
            QLabel#settingFieldCaption {
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                border: none;
                background-color: transparent;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #dce3ec;
                border-radius: 14px;
                margin-top: 14px;
                padding: 16px 12px 12px 12px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 16px;
                padding: 0 8px;
                color: #243247;
                background-color: #ffffff;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
            QKeySequenceEdit, QPlainTextEdit, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                padding: 7px 10px;
                min-height: 25px;
                selection-background-color: #4f46e5;
            }
            QLineEdit:hover, QComboBox:hover, QSpinBox:hover,
            QDoubleSpinBox:hover, QKeySequenceEdit:hover {
                border-color: #94a3b8;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
            QDoubleSpinBox:focus, QKeySequenceEdit:focus {
                border: 2px solid #4f46e5;
                padding: 6px 9px;
                background-color: #ffffff;
            }
            QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
            QDoubleSpinBox:disabled, QKeySequenceEdit:disabled {
                color: #94a3b8;
                background-color: #f1f5f9;
                border-color: #e2e8f0;
            }
            QComboBox {
                color: #263449;
                padding-right: 38px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 34px;
                border: none;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: #f8fafc;
            }
            QComboBox::drop-down:hover {
                background-color: #eef2ff;
            }
            QComboBox::drop-down:pressed {
                background-color: #e0e7ff;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QSpinBox, QDoubleSpinBox {
                padding-right: 30px;
                font-weight: 600;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 25px;
                border: none;
                border-left: 1px solid #d6deea;
                border-bottom: 1px solid #d6deea;
                border-top-right-radius: 8px;
                background-color: #f1f5f9;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 25px;
                border: none;
                border-left: 1px solid #d6deea;
                border-bottom-right-radius: 8px;
                background-color: #f1f5f9;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #e0e7ff;
            }
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
                background-color: #c7d2fe;
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
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                padding: 7px 16px;
                min-height: 28px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #3730a3;
                border-color: #818cf8;
                background-color: #eef2ff;
            }
            QPushButton:pressed {
                background-color: #e0e7ff;
                padding-top: 8px;
                padding-bottom: 6px;
            }
            QPushButton:disabled {
                color: #a0aec0;
                border-color: #e2e8f0;
                background-color: #f4f6f9;
            }
            QPushButton#primaryActionButton {
                color: white;
                font-size: 16px;
                font-weight: 700;
                border: none;
                background-color: #4f46e5;
            }
            QPushButton#primaryActionButton:hover {
                background-color: #4338ca;
            }
            QPushButton#primaryActionButton:pressed {
                background-color: #3730a3;
            }
            QPushButton#secondaryActionButton {
                color: white;
                border: none;
                background-color: #2563eb;
            }
            QPushButton#secondaryActionButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#settingsButton {
                color: white;
                font-size: 13px;
                border: 1px solid #c7d2fe;
                background-color: #eef2ff;
                color: #3730a3;
            }
            QPushButton#settingsButton:hover {
                background-color: #e0e7ff;
                border-color: #818cf8;
            }
            QPushButton#helpActionButton {
                color: #475569;
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
            }
            QPushButton#helpActionButton:hover {
                color: #3730a3;
                border-color: #a5b4fc;
                background-color: #eef2ff;
            }
            QPushButton#dangerOutlineButton {
                color: #dc2626;
                border: 1px solid #f0a4a4;
                background-color: #ffffff;
            }
            QPushButton#dangerOutlineButton:hover {
                color: #ffffff;
                border-color: #dc2626;
                background-color: #dc2626;
            }
            QCheckBox {
                spacing: 8px;
                min-height: 24px;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d8e1ed;
                border-radius: 10px;
                padding: 7px;
                outline: none;
            }
            QListWidget::item {
                min-height: 36px;
                padding: 6px 10px;
                margin: 2px 0;
                border-radius: 7px;
            }
            QListWidget::item:hover {
                color: #4f46c7;
                background-color: #f0efff;
            }
            QListWidget::item:selected {
                color: white;
                background-color: #6657d9;
            }
            QPlainTextEdit {
                background-color: #151b2b;
                color: #e5edf7;
                border-color: #202b3f;
                font-family: Menlo, Consolas, monospace;
            }
            QPushButton#carouselButton {
                color: #5b53c7;
                font-size: 19px;
                padding: 0;
                border-radius: 8px;
                background-color: #f0efff;
                border: 1px solid #d5d0ff;
            }
            QPushButton#carouselButton:hover {
                color: #ffffff;
                background-color: #6657d9;
                border-color: #6657d9;
            }
            QSplitter::handle {
                background-color: #dde5ef;
                border-radius: 2px;
                margin: 10px 4px;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #9f98e8;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 11px;
                margin: 3px 2px;
            }
            QScrollBar::handle:vertical {
                background: #c5cfdd;
                min-height: 32px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9eabc0;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 11px;
                margin: 2px 3px;
            }
            QScrollBar::handle:horizontal {
                background: #c5cfdd;
                min-width: 32px;
                border-radius: 4px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
                height: 0px;
            }
            QMenu {
                color: #263449;
                background-color: #ffffff;
                border: 1px solid #d8e1ed;
                border-radius: 9px;
                padding: 7px;
            }
            QMenu::item {
                padding: 8px 28px 8px 12px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                color: #4f46c7;
                background-color: #f0efff;
            }
            QFrame#nametagPickerPopup {
                background-color: #ffffff;
                border: 1px solid #d8e1ed;
                border-radius: 10px;
            }
            QLabel#nametagPickerTitle {
                color: #334155;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#nametagPickerEmpty {
                color: #94a3b8;
                padding: 16px 8px;
            }
            QFrame#nametagPickerRow {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QFrame#nametagPickerRow:hover {
                background-color: #eef2ff;
                border-color: #c7d2fe;
            }
            QFrame#nametagPickerRow[current="true"] {
                background-color: #e0e7ff;
                border-color: #818cf8;
            }
            QLabel#nametagPickerThumb {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
            QLabel#nametagPickerName {
                color: #1e293b;
                font-weight: 600;
            }
            QPushButton#nametagDeleteButton {
                color: #94a3b8;
                border: none;
                background-color: transparent;
                min-height: 22px;
                padding: 0;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#nametagDeleteButton:hover {
                color: #ffffff;
                background-color: #dc2626;
                border-radius: 12px;
            }
            QStatusBar {
                color: #64748b;
                background-color: #ffffff;
                border-top: 1px solid #e2e8f0;
            }
            QToolTip {
                color: #ffffff;
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 6px 8px;
            }
            """
        )

    def setup_advance_setting_tab(self):
        tab_advance_setting = QWidget()

        # Two vertical layouts side-by-side
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # Distribute group boxes evenly between columns
        self.advance_settings_gboxes = {}  # store title -> QGroupBox mapping
        for idx, title in enumerate(self.cfg):
            # Skip hide settings
            if title in ADV_SETTINGS_HIDE:
                continue
            gbox = create_advance_setting_gbox(title, self.cfg,
                                               self.comments,
                                               self.comments_section)
            self.advance_settings_gboxes[title] = gbox
            if idx % 2 == 0:
                left_col.addWidget(gbox)
            else:
                right_col.addWidget(gbox)

        # Wrap columns in a horizontal layout
        row_layout = QHBoxLayout()
        row_layout.addLayout(left_col)
        row_layout.addLayout(right_col)

        # Make it scrollable (recommended for lots of settings)
        scroll_area = QScrollArea()
        container = QWidget()
        container.setLayout(row_layout)
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)

        # Final layout for the tab
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll_area)
        tab_advance_setting.setLayout(final_layout)

        return tab_advance_setting


    def setup_shutdown_monitor_tab(self):
        """Tab: timed shutdown + lost-character auto-shutdown."""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        tab.setLayout(layout)

        gbox = QGroupBox("定时关机")
        gbox_layout = QVBoxLayout()
        gbox_layout.setSpacing(10)
        gbox.setLayout(gbox_layout)

        row1 = QHBoxLayout()
        self.chk_shutdown_timed = QCheckBox("启用定时关机")
        self.chk_shutdown_timed.setToolTip(
            "勾选后可设置关机时间；到点执行 Windows shutdown /s（短倒计时，可取消）"
        )
        self.time_shutdown_at = QTimeEdit()
        self.time_shutdown_at.setDisplayFormat("HH:mm")
        self.time_shutdown_at.setTime(QTime(3, 0))
        self.time_shutdown_at.setEnabled(False)
        row1.addWidget(self.chk_shutdown_timed)
        row1.addWidget(QLabel("关机时间"))
        row1.addWidget(self.time_shutdown_at)
        row1.addStretch(1)
        gbox_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.chk_shutdown_lost = QCheckBox("找不到主角时自动关机")
        self.chk_shutdown_lost.setToolTip(
            "挂机运行中，页面连续找不到主角超过设定秒数后自动关机"
        )
        self.spin_shutdown_lost_seconds = ModernSpinBox()
        self.spin_shutdown_lost_seconds.setRange(5, 86400)
        self.spin_shutdown_lost_seconds.setValue(60)
        self.spin_shutdown_lost_seconds.setSuffix(" 秒")
        self.spin_shutdown_lost_seconds.setEnabled(False)
        row2.addWidget(self.chk_shutdown_lost)
        row2.addWidget(QLabel("超时"))
        row2.addWidget(self.spin_shutdown_lost_seconds)
        row2.addStretch(1)
        gbox_layout.addLayout(row2)

        hint = QLabel(
            "说明：触发后执行 shutdown /s /t 60（约 60 秒后关机）。"
            "倒计时期间取消勾选会执行 shutdown /a 取消关机。"
            "「找不到主角」仅在挂机引擎运行时生效；定时关机由设置里的时钟监控。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b;")
        gbox_layout.addWidget(hint)

        self.lbl_shutdown_status = QLabel("状态：未启用")
        self.lbl_shutdown_status.setStyleSheet("color: #0f172a; font-weight: 600;")
        gbox_layout.addWidget(self.lbl_shutdown_status)

        layout.addWidget(gbox)
        layout.addStretch(1)

        self.chk_shutdown_timed.toggled.connect(self._on_shutdown_timed_toggled)
        self.chk_shutdown_lost.toggled.connect(self._on_shutdown_lost_toggled)
        self.time_shutdown_at.timeChanged.connect(self._on_shutdown_monitor_changed)
        self.spin_shutdown_lost_seconds.valueChanged.connect(self._on_shutdown_monitor_changed)

        self._shutdown_fired_date = None
        self._shutdown_pending = False
        return tab

    def _shutdown_monitor_cfg(self):
        return self.cfg.setdefault(
            "shutdown_monitor",
            {
                "timed_enable": False,
                "timed_at": "03:00",
                "lost_enable": False,
                "lost_seconds": 60,
                "shutdown_delay_sec": 60,
            },
        )

    def _apply_shutdown_monitor_to_ui(self):
        if not hasattr(self, "chk_shutdown_timed"):
            return
        sm = self._shutdown_monitor_cfg()
        self.chk_shutdown_timed.blockSignals(True)
        self.chk_shutdown_lost.blockSignals(True)
        self.time_shutdown_at.blockSignals(True)
        self.spin_shutdown_lost_seconds.blockSignals(True)
        try:
            self.chk_shutdown_timed.setChecked(bool(sm.get("timed_enable", False)))
            self.chk_shutdown_lost.setChecked(bool(sm.get("lost_enable", False)))
            self.time_shutdown_at.setEnabled(self.chk_shutdown_timed.isChecked())
            self.spin_shutdown_lost_seconds.setEnabled(self.chk_shutdown_lost.isChecked())
            hhmm = str(sm.get("timed_at", "03:00") or "03:00")
            try:
                hh, mm = hhmm.split(":")[:2]
                self.time_shutdown_at.setTime(QTime(int(hh), int(mm)))
            except Exception:
                self.time_shutdown_at.setTime(QTime(3, 0))
            self.spin_shutdown_lost_seconds.setValue(int(sm.get("lost_seconds", 60) or 60))
        finally:
            self.chk_shutdown_timed.blockSignals(False)
            self.chk_shutdown_lost.blockSignals(False)
            self.time_shutdown_at.blockSignals(False)
            self.spin_shutdown_lost_seconds.blockSignals(False)
        self._refresh_shutdown_status_label()

    def _collect_shutdown_monitor_from_ui(self):
        sm = self._shutdown_monitor_cfg()
        sm["timed_enable"] = bool(self.chk_shutdown_timed.isChecked())
        sm["lost_enable"] = bool(self.chk_shutdown_lost.isChecked())
        t = self.time_shutdown_at.time()
        sm["timed_at"] = f"{t.hour():02d}:{t.minute():02d}"
        sm["lost_seconds"] = int(self.spin_shutdown_lost_seconds.value())
        sm.setdefault("shutdown_delay_sec", 60)
        return sm

    def _on_shutdown_timed_toggled(self, checked):
        self.time_shutdown_at.setEnabled(bool(checked))
        if not checked:
            self._cancel_windows_shutdown("取消定时关机")
            self._shutdown_fired_date = None
        self._on_shutdown_monitor_changed()

    def _on_shutdown_lost_toggled(self, checked):
        self.spin_shutdown_lost_seconds.setEnabled(bool(checked))
        if not checked:
            self._cancel_windows_shutdown("取消「找不到主角」关机")
        self._on_shutdown_monitor_changed()

    def _on_shutdown_monitor_changed(self, *_args):
        sm = self._collect_shutdown_monitor_from_ui()
        self._refresh_shutdown_status_label()
        # Push live copy into running engine (if any) so lost-monitor toggles apply immediately.
        try:
            engine = None
            ctrl = getattr(self, "controller", None)
            if ctrl is not None:
                engine = (
                    getattr(ctrl, "bot", None)
                    or getattr(ctrl, "engine", None)
                    or getattr(ctrl, "maple", None)
                )
            if engine is not None and isinstance(getattr(engine, "cfg", None), dict):
                engine.cfg["shutdown_monitor"] = copy.deepcopy(sm)
                # Re-arm lost trigger when user re-enables
                if not sm.get("lost_enable"):
                    if hasattr(engine, "_shutdown_lost_fired"):
                        engine._shutdown_lost_fired = False
                    if hasattr(engine, "_shutdown_lost_since"):
                        engine._shutdown_lost_since = None
        except Exception as err:
            logger.debug(f"[ShutdownMonitor] live engine sync: {err}")
        # Persist into active custom yaml (same path as Save)
        try:
            path = getattr(self, "path_cfg_custom", None)
            if path and "config_default.yaml" not in str(path):
                cfg_to_save = copy.deepcopy(self.cfg)
                try:
                    reset_profession_overrides(cfg_to_save, self.cfg_fallback)
                except Exception:
                    try:
                        reset_profession_overrides(cfg_to_save, self.cfg_base)
                    except Exception:
                        pass
                try:
                    cfg_diff = get_cfg_diff(self.cfg_base, cfg_to_save)
                    save_yaml(cfg_diff, path)
                except NameError:
                    # Fallback symbol names used in some builds
                    try:
                        cfg_diff = get_cfg_diff(self.cfg_base, cfg_to_save)
                        save_yaml(cfg_diff, path)
                    except Exception as persist_err:
                        logger.debug(f"[ShutdownMonitor] persist: {persist_err}")
                except Exception as persist_err:
                    logger.debug(f"[ShutdownMonitor] persist: {persist_err}")
        except Exception as err:
            logger.debug(f"[ShutdownMonitor] change handler: {err}")

    def _refresh_shutdown_status_label(self):
        if not hasattr(self, "lbl_shutdown_status"):
            return
        sm = self._shutdown_monitor_cfg()
        parts = []
        if sm.get("timed_enable"):
            parts.append(f"定时 {sm.get('timed_at', '?')}")
        if sm.get("lost_enable"):
            parts.append(f"丢主角 {int(sm.get('lost_seconds', 60))} 秒")
        if getattr(self, "_shutdown_pending", False):
            parts.append("关机倒计时中（取消勾选可 abort）")
        if not parts:
            self.lbl_shutdown_status.setText("状态：未启用")
        else:
            self.lbl_shutdown_status.setText("状态：已启用 — " + "；".join(parts))

    def _start_shutdown_monitor_timer(self):
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(1000)
        self._shutdown_timer.timeout.connect(self._tick_shutdown_monitor)
        self._shutdown_timer.start()

    def _tick_shutdown_monitor(self):
        if not hasattr(self, "chk_shutdown_timed"):
            return
        sm = self._collect_shutdown_monitor_from_ui()
        if not sm.get("timed_enable"):
            return
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        if self._shutdown_fired_date == today:
            return
        try:
            hh, mm = str(sm.get("timed_at", "03:00")).split(":")[:2]
            target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except Exception:
            return
        if now >= target and (now - target).total_seconds() < 60:
            delay = int(sm.get("shutdown_delay_sec", 60) or 60)
            if self._request_windows_shutdown(delay, reason=f"定时关机到点 {sm.get('timed_at')}"):
                self._shutdown_fired_date = today

    def _request_windows_shutdown(self, delay_sec, reason=""):
        delay_sec = max(0, int(delay_sec))
        try:
            cmd = f"cmd /c shutdown /s /t {delay_sec}"
            subprocess.Popen(cmd, shell=True)
            self._shutdown_pending = True
            msg = f"[ShutdownMonitor] 已请求关机：{cmd} ({reason})"
            logger.warning(msg)
            if hasattr(self, "lbl_shutdown_status"):
                self.lbl_shutdown_status.setText(
                    f"状态：已触发关机倒计时 {delay_sec}s — {reason}"
                )
            try:
                self.statusBar().showMessage(msg, 8000)
            except Exception:
                pass
            return True
        except Exception as err:
            logger.error(f"[ShutdownMonitor] 关机请求失败: {err}")
            return False

    def _cancel_windows_shutdown(self, reason=""):
        try:
            subprocess.Popen("cmd /c shutdown /a", shell=True)
            if getattr(self, "_shutdown_pending", False):
                logger.info(f"[ShutdownMonitor] 已取消关机倒计时 ({reason})")
            self._shutdown_pending = False
            self._refresh_shutdown_status_label()
        except Exception as err:
            logger.error(f"[ShutdownMonitor] 取消关机失败: {err}")


    def setup_game_window_viz_tab(self):
        tab_game_window_viz = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        tab_game_window_viz.setLayout(layout)

        # The engine emits its annotated video layer only while this tab is active.
        self._debug_source_pixmap = QPixmap()
        self.debug_canvas = QLabel()
        clear_debug_canvas(self.debug_canvas)
        self.debug_canvas.setText("启动后将在这里显示视频图层识别结果")
        self.debug_canvas.setAlignment(Qt.AlignCenter)
        self.debug_canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.debug_canvas.setMinimumSize(0, 0)
        self.debug_canvas.setStyleSheet(
            "background-color: #0b1020; color: #cbd5e1; "
            "border: 1px solid #202b3f; border-radius: 12px;"
        )
        monitor_splitter = QSplitter(Qt.Horizontal)
        monitor_splitter.setChildrenCollapsible(False)
        monitor_splitter.addWidget(self.debug_canvas)
        self.tab_route_map_viz.setMinimumWidth(220)
        self.tab_route_map_viz.setMaximumWidth(380)
        monitor_splitter.addWidget(self.tab_route_map_viz)
        monitor_splitter.setStretchFactor(0, 3)
        monitor_splitter.setStretchFactor(1, 1)
        monitor_splitter.setSizes([760, 270])
        layout.addWidget(monitor_splitter, 1)

        return tab_game_window_viz

    def setup_route_map_viz_tab(self):
        tab_route_map_viz_tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(8)
        tab_route_map_viz_tab.setLayout(layout)

        title = QLabel("路线总览")
        title.setStyleSheet("font-weight: 600; color: #475569;")
        layout.addWidget(title)

        # The route overview is generated separately from the exact navigation pixels.
        self._route_source_pixmap = QPixmap()
        self.route_map_canvas = QLabel()
        clear_debug_canvas(self.route_map_canvas)
        self.route_map_canvas.setText("路线模式运行后显示路线、玩家位置和当前视野")
        self.route_map_canvas.setAlignment(Qt.AlignCenter)
        self.route_map_canvas.setWordWrap(True)
        self.route_map_canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.route_map_canvas.setMinimumSize(0, 0)
        self.route_map_canvas.setStyleSheet(
            "background-color: #111820; color: #94a3b8; "
            "border: 1px solid #273244; border-radius: 12px; padding: 8px;"
        )
        layout.addWidget(self.route_map_canvas, 1)

        return tab_route_map_viz_tab

    def save_ui_state(self):
        path = os.path.join(os.path.expanduser("~"), ".maplebot_ui_state.json")
        state = {
            "last_config_path": self.path_cfg_custom
        }
        with open(path, 'w') as f:
            json.dump(state, f)
        logger.info(f"[UI] Save UI state to {path}")

    def load_ui_state(self):
        path = os.path.join(os.path.expanduser("~"), ".maplebot_ui_state.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                state = json.load(f)
                # Load config
                self.load_config(create_error_label(),
                                 state.get("last_config_path"))
        logger.info(f"[UI] Load UI state from {path}")


    def create_attack_gbox(self):
        '''
        Create attack group box using two-column QFormLayouts
        '''
        gbox = QGroupBox("⚔️ Attack Settings")

        # Left column
        form_left = QFormLayout()
        self.attack_mode = QComboBox()
        self.attack_mode.addItems(["Basic", "AOE Skill", "Hybrid"])
        self.attack_mode.setFixedWidth(120)

        # Connect dropdown change to handler
        self.attack_mode.currentIndexChanged.connect(
            self.update_atk_config_trigger_by_drop_list
        )

        # Set default value
        form_left.addRow("Attack Mode:", self.attack_mode)

        self.attack_range_x = QLineEdit()
        self.attack_range_x.setFixedWidth(60)
        form_left.addRow("Range X:", self.attack_range_x)

        # Right column
        form_right = QFormLayout()
        self.attack_cooldown = QLineEdit()
        self.attack_cooldown.setFixedWidth(60)
        form_right.addRow("Cooldown (s):", self.attack_cooldown)

        self.attack_range_y = QLineEdit()
        self.attack_range_y.setFixedWidth(60)
        form_right.addRow("Range Y:", self.attack_range_y)

        # Combine left and right forms
        columns = QHBoxLayout()
        columns.addLayout(form_left)
        columns.addSpacing(20)
        columns.addLayout(form_right)

        # Field validation
        error_label = create_error_label()
        self.attack_range_x.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_range_x.text(), error_label, 0, 9999))
        self.attack_range_y.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_range_y.text(), error_label, 0, 9999))
        self.attack_cooldown.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_cooldown.text(), error_label, 0, 9999))

        # Final layout
        layout = QVBoxLayout()
        layout.addWidget(error_label)
        layout.addLayout(columns)
        gbox.setLayout(layout)
        return gbox

    def create_key_binding_gbox(self):
        gbox = QGroupBox("🎮 Key Bindings")
        hbox = QHBoxLayout()

        # Left Column
        form_left = QFormLayout()
        self.basic_attack_key = SingleKeyEdit()
        self.basic_attack_key.setFixedWidth(100)
        form_left.addRow("Basic Attack:", self.basic_attack_key)

        self.teleport_key = SingleKeyEdit()
        self.teleport_key.setFixedWidth(100)
        form_left.addRow("Teleport:", self.teleport_key)

        self.party_key = SingleKeyEdit()
        self.party_key.setFixedWidth(100)
        form_left.addRow("Party:", self.party_key)

        # Right Column
        form_right = QFormLayout()
        self.aoe_skill_key = SingleKeyEdit()
        self.aoe_skill_key.setFixedWidth(100)
        form_right.addRow("AOE Skill:", self.aoe_skill_key)

        self.jump_key = SingleKeyEdit()
        self.jump_key.setFixedWidth(100)
        form_right.addRow("Jump:", self.jump_key)

        self.return_home_key = SingleKeyEdit()
        self.return_home_key.setFixedWidth(100)
        form_right.addRow("Home:", self.return_home_key)

        # Combine left and right column form
        hbox.addLayout(form_left)
        hbox.addSpacing(20)  # space between columns
        hbox.addLayout(form_right)
        gbox.setLayout(hbox)
        return gbox

    def create_buff_skill_section(self):
        '''
        Create buff skill section with toggle checkbox and dynamic rows
        '''
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignLeft)
        container.setLayout(layout)

        # Auto Buff checkbox
        self.checkbox_enable_buff = QCheckBox("Auto Buff")
        self.checkbox_enable_buff.stateChanged.connect(self.toggle_auto_buff)
        layout.addWidget(self.checkbox_enable_buff, alignment=Qt.AlignLeft)

        # Buff section (initially hidden)
        self.buff_section_container = QWidget()
        self.buff_section_container.setVisible(False)
        buff_section_layout = QVBoxLayout()
        buff_section_layout.setContentsMargins(0, 0, 0, 0)
        buff_section_layout.setSpacing(2)
        buff_section_layout.setAlignment(Qt.AlignLeft)
        self.buff_section_container.setLayout(buff_section_layout)

        # Buff rows layout
        self.buff_layout = QVBoxLayout()
        self.buff_layout.setSpacing(2)
        self.buff_layout.setAlignment(Qt.AlignLeft)
        self.buff_inputs = []

        # Initial buff row
        self.add_buff_row()

        # Add dynamic row layout + button
        buff_section_layout.addLayout(self.buff_layout)

        self.button_add_buff = QPushButton("+ Add Buff Key")
        self.button_add_buff.setFixedWidth(100)
        self.button_add_buff.clicked.connect(self.add_buff_row)
        buff_section_layout.addWidget(self.button_add_buff, alignment=Qt.AlignLeft)

        layout.addWidget(self.buff_section_container)

        return container

    def create_pet_skill_gbox(self):
        gbox = QGroupBox("❤️ Pet Skills")
        layout_form = QFormLayout()

        # Auto Add HP checkbox
        hp_row = QHBoxLayout()
        self.checkbox_auto_add_hp = QCheckBox("Auto Add HP")
        self.checkbox_auto_add_hp.stateChanged.connect(self.toggle_auto_add_hp)
        hp_row.addWidget(self.checkbox_auto_add_hp)
        # Auto Add HP settings
        self.hp_input_widget, self.add_hp_percent, self.add_hp_key = self.create_hp_mp_widget("HP")
        self.hp_input_widget.setVisible(False) # Hide setting on default
        hp_row.addWidget(self.hp_input_widget)
        # Validation HP percent
        error_label_hp = create_error_label()
        self.add_hp_percent.editingFinished.connect(
            lambda: validate_numerical_input(self.add_hp_percent.text(), error_label_hp, 0, 100))
        # Add to layout
        layout_form.addWidget(error_label_hp)
        layout_form.addRow(hp_row)

        # Auto add MP checkbox
        mp_row = QHBoxLayout()
        self.checkbox_auto_add_mp = QCheckBox("Auto Add MP")
        self.checkbox_auto_add_mp.stateChanged.connect(self.toggle_auto_add_mp)
        mp_row.addWidget(self.checkbox_auto_add_mp)
        # Auto Add MPHP settings
        self.mp_input_widget, self.add_mp_percent, self.add_mp_key = self.create_hp_mp_widget("MP")
        self.mp_input_widget.setVisible(False)
        mp_row.addWidget(self.mp_input_widget)
        # Validation MP percent
        error_label_mp = create_error_label()
        self.add_mp_percent.editingFinished.connect(
            lambda: validate_numerical_input(self.add_mp_percent.text(), error_label_mp, 0, 100))
        # Add to layout
        layout_form.addWidget(error_label_mp)
        layout_form.addRow(mp_row)

        # Buff skill section
        layout_form.addRow(self.create_buff_skill_section())

        gbox.setLayout(layout_form)
        return gbox

    def create_map_selection_gbox(self):
        '''
        Creates a group box containing the scroll list for map selection
        '''
        gbox = QGroupBox("地图选择")

        # Load map list from directory
        self.list_widget_maps = QListWidget()
        self.list_widget_maps.itemClicked.connect(self.on_map_selected)
        minimap_dir = MINIMAPS
        for name in os.listdir(minimap_dir):
            if name.startswith("."):
                continue  # Skip hidden/system files

            if name in self.data["eng_to_cn"]:
                name_cn = self.data["eng_to_cn"][name]
                full_path = os.path.join(minimap_dir, name)
                if os.path.isdir(full_path):
                    # self.list_widget_maps.addItem(f"{name} ({name_cn})")
                    display_text = f"{name} ({name_cn})"
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, name)
                    self.list_widget_maps.addItem(item)

        layout = QVBoxLayout()
        self.label_map_info = QLabel("请选择练级地图：")
        layout.addWidget(self.label_map_info)
        layout.addWidget(self.list_widget_maps)
        gbox.setLayout(layout)
        return gbox

    def create_log_gbox(self):
        gbox = QGroupBox("运行日志")
        layout = QVBoxLayout()

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.log_output)
        gbox.setLayout(layout)

        # Create Qt logger handler
        self.qt_log_handler = QtLogHandler()
        self.qt_log_handler.log_signal.connect(self.append_log)
        self.qt_log_handler.setFormatter(
            logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%H:%M:%S'))

        # Add it to your logger
        logger.addHandler(self.qt_log_handler)

        return gbox

    def create_control_gbox(self):
        '''
        Creates a group box with hotkey instructions and a dropdown to select mode
        '''
        gbox = QGroupBox("🕹️ Bot Control")
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # Load Config Section
        self.load_config_error_label = create_error_label()
        layout.addWidget(self.load_config_error_label)  # Add above the button

        load_config_layout = QHBoxLayout()
        load_config_layout.setSpacing(8)
        load_config_layout.setAlignment(Qt.AlignLeft)

        self.button_load_config = QPushButton("📂 Load Config")
        self.button_load_config.clicked.connect(
            lambda: self.load_config(self.load_config_error_label)
        )
        self.label_config_path = QLabel("(No config loaded)")

        load_config_layout.addWidget(self.button_load_config)
        load_config_layout.addWidget(self.label_config_path)

        # --- Control Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setAlignment(Qt.AlignLeft)

        # Start / Pause Button
        self.button_start_pause = QPushButton("▶ Start (F1)")
        self.button_start_pause.setCheckable(True)
        self.button_start_pause.clicked.connect(self.toggle_start_ui)

        # Screenshot Button
        self.button_screenshot = QPushButton("📸 Screenshot (F2)")
        self.button_screenshot.clicked.connect(self.toggle_screenshot_ui)

        # Record Button
        self.button_record = QPushButton("⏺ Record (F3)")
        self.button_record.setCheckable(True)
        self.button_record.clicked.connect(self.toggle_record_ui)

        # Bot Mode Dropdown
        layout_bot_mode = QHBoxLayout()
        layout_bot_mode.setSpacing(8)
        self.bot_mode = QComboBox()
        self.bot_mode.addItem("normal", "normal")
        self.bot_mode.addItem("aux", "aux")
        self.bot_mode.addItem("patrol", "patrol")
        self.bot_mode.addItem("smart_patrol", "smart_patrol")

        layout_bot_mode.addWidget(QLabel("Bot Mode:"))
        layout_bot_mode.addWidget(self.bot_mode)
        layout_bot_mode.setAlignment(Qt.AlignLeft)

        button_layout.addWidget(self.button_start_pause)
        button_layout.addWidget(self.button_screenshot)
        button_layout.addWidget(self.button_record)
        button_layout.addLayout(layout_bot_mode)

        layout.addLayout(button_layout)
        layout.addLayout(load_config_layout)

        gbox.setLayout(layout)
        return gbox
        logger.info(f"[UI] Map selected: {map_name}")

    def create_attack_widget(self):
        '''
        Create a wedge widget: "Press key ➜ [KEY] for Mode A/B"
        '''
        layout_main = QHBoxLayout()

        layout_main.addWidget(QLabel("Attack Key:"))
        key_input = SingleKeyEdit()
        key_input.setFixedWidth(100)
        layout_main.addWidget(key_input)

        # Horizontal Range
        layout_main.addWidget(QLabel("Range X:"))
        range_x = QLineEdit()
        range_x.setPlaceholderText("50")
        range_x.setFixedWidth(60)
        layout_main.addWidget(range_x)

        # Vertical Range
        layout_main.addWidget(QLabel("Range Y:"))
        range_y = QLineEdit()
        range_y.setPlaceholderText("50")
        range_y.setFixedWidth(60)
        layout_main.addWidget(range_y)

        # CoolDown
        layout_main.addWidget(QLabel("CoolDown (s):"))
        cooldown = QLineEdit()
        cooldown.setPlaceholderText("0.1")
        cooldown.setFixedWidth(60)
        layout_main.addWidget(cooldown)

        container = QWidget()
        container.setLayout(layout_main)

        return container, key_input, range_x, range_y, cooldown

    def create_hp_mp_widget(self, title):
        '''
        Creates a widget for Auto HP/MP usage with tight label-field alignment
        '''
        container = QWidget()
        layout_main = QVBoxLayout()
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.setSpacing(2)

        # Input line
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(2)
        input_layout.setAlignment(Qt.AlignLeft)

        label_1 = QLabel(f"When {title} is below:")
        label_1.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        percent = QLineEdit()
        percent.setPlaceholderText("50")
        percent.setFixedWidth(60)

        label_2 = QLabel("%, press ")
        label_2.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        input_key = SingleKeyEdit()
        input_key.setFixedWidth(100)

        label_3 = QLabel("key.")
        label_3.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        # Add to layout
        input_layout.addWidget(label_1)
        input_layout.addWidget(percent)
        input_layout.addWidget(label_2)
        input_layout.addWidget(input_key)
        input_layout.addWidget(label_3)

        layout_main.addLayout(input_layout)
        container.setLayout(layout_main)

        return container, percent, input_key

    def load_config(self, error_label, path=None):
        '''
        Load config_custom.yaml from file and apply settings to UI
        '''
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Config File", "", "YAML Files (*.yaml);;All Files (*)"
            )
            if not path:
                return  # User canceled

        # Validation
        if not path.endswith(".yaml"):
            error_label.setText("Only .yaml files are supported.")
            error_label.setVisible(True)
            return

        # Validate the file name
        if "config_default.yaml" in path or "config_data.yaml" in path or \
           "config_macOS.yaml" in path:
            error_label.setText(f"{path} cannot be loaded as customized yaml")
            error_label.setVisible(True)
            return

        error_label.setVisible(False)
        if hasattr(self, "label_config_path"):
            self.label_config_path.setText(path)
            self.label_config_path.setStyleSheet("color: green")
        self.statusBar().showMessage(f"状态：已加载配置 {path}")

        # Load customized yaml (always merge with default base — never replace)
        try:
            custom_cfg = load_yaml(path)
            if not isinstance(custom_cfg, dict):
                custom_cfg = {}
            # These retired features may still exist in a config last saved by
            # v30/v31. Ignore them so closing this version cleans the stale data.
            custom_cfg.pop("auto_pickup", None)
            custom_cfg.pop("lie_detector", None)
            if not custom_cfg:
                logger.warning(
                    f"[UI] Config file is empty/{{}}: {path} — UI will show defaults only"
                )
            self.cfg_fallback = override_cfg(copy.deepcopy(self.cfg_base), custom_cfg)
            self.cfg = copy.deepcopy(self.cfg_fallback)
            self.path_cfg_custom = path
            # Keep raw custom so apply_config_to_ui can re-layer it over profession overrides.
            self._loaded_custom_cfg = copy.deepcopy(custom_cfg)
        except FileNotFoundError:
            logger.warning(f"[UI] Unable to find config file: {path}")
            error_label.setText(f"找不到配置文件：{path}")
            error_label.setVisible(True)
            return
        except Exception as error:
            logger.exception(f"[UI] Load config failed: {error}")
            error_label.setText(f"加载失败：{error}")
            error_label.setVisible(True)
            try:
                QMessageBox.warning(self, "加载失败", str(error))
            except Exception:
                pass
            return

        # Re-apply config to UI (YAML wins over profession combat overrides)
        try:
            self.apply_config_to_ui(prefer_loaded_custom=True)
        except Exception as error:
            logger.exception(f"[UI] apply_config_to_ui after load failed: {error}")
            error_label.setText(f"配置已读入但刷新界面失败：{error}")
            error_label.setVisible(True)
            try:
                QMessageBox.warning(self, "加载部分失败", str(error))
            except Exception:
                pass

    def update_atk_config_trigger_by_drop_list(self):
        '''
        Update attack config fields based on selected attack mode from drop-down.
        '''
        index = self.attack_mode.currentIndex()  # Get selected index
        if index == 0:
            atk_cfg = self.cfg["directional_attack"]
        elif index == 1:
            atk_cfg = self.cfg["aoe_skill"]
        elif index == 2:
            atk_cfg = self.cfg["directional_attack"]
        else:
            atk_cfg = None

        if atk_cfg:
            self.attack_range_x.setText(str(atk_cfg["range_x"]))
            self.attack_cooldown.setText(str(atk_cfg["cooldown"]))
            self.attack_range_y.setText(str(atk_cfg["range_y"]))

    def apply_config_to_ui(self, prefer_loaded_custom=False):
        # YAML_WINS_OVER_PROFESSION_ON_LOAD_V1
        selected_profession = self.profession_combo.currentData() or ""
        self.profession_store.apply_to_cfg(
            self.cfg, selected_profession, self.cfg_fallback
        )
        # Loading a YAML must override homepage combat fields for the selected profession.
        # Profession select still applies overrides via on_profession_selected.
        if prefer_loaded_custom:
            custom = getattr(self, "_loaded_custom_cfg", None)
            if isinstance(custom, dict) and custom:
                override_cfg(self.cfg, copy.deepcopy(custom))

        self.window_title_edit.setText(self.cfg["game_window"].get("title", ""))
        selected_nametag = (
            self.cfg.get("nametag", {}).get("name", "")
            if self.cfg.get("nametag", {}).get("enable") else ""
        )
        self.character_name_edit.setText(selected_nametag or "")
        # Re-bind nametag assets (layers / enable) when a name is present so
        # load does not leave 名片 looking empty despite yaml keys existing.
        if selected_nametag:
            try:
                self.apply_character_nametag(selected_nametag, quiet=True)
            except Exception as err:
                logger.warning(f"[UI] apply_character_nametag after load failed: {err}")

        hm_cfg = self.cfg["health_monitor"]
        self.home_hp_percent.setValue(int(hm_cfg.get("add_hp_percent", 0)))
        self.home_mp_percent.setValue(int(hm_cfg.get("add_mp_percent", 0)))
        self._sync_home_attack_fields_from_cfg()
        mode_value = self.cfg["bot"].get("mode", "normal")
        mode_index = self.bot_mode.findData(mode_value)
        self._suppress_bot_mode_handler = True
        try:
            self.bot_mode.setCurrentIndex(max(mode_index, 0))
        finally:
            self._suppress_bot_mode_handler = False
        if mode_value == "aux":
            # Assist mode always uses classic single-press heal.
            self._force_disable_potion_profile_for_assist(persist=False)

        # Map Selection
        self.map_management_tab.select_map(self.cfg["bot"].get("map", ""))

        # Advance settings
        self.update_advance_setting_ui_from_cfg()
        self._apply_shutdown_monitor_to_ui()

    def set_gbox_enabled(self, enabled: bool):
        gboxs = [
            self.profession_gbox,
            self.function_gbox,
        ]
        gboxs += list(self.advance_settings_gboxes.values())
        for gbox in gboxs:
            gbox.setEnabled(enabled)
        self.map_management_tab.setEnabled(enabled)
        self.monster_management_tab.setEnabled(enabled)
        self.record_tab.setEnabled(enabled)
        self.button_settings.setEnabled(enabled)

    def on_tab_changed(self, index):
        tab_name = self.tabs.tabText(index)
        tab_key = tab_name.split(" ", 1)[-1]
        if tab_key == "运行监控":
            self.controller.enable_bot_viz()

        elif tab_key == "路线地图":
            self.controller.enable_bot_viz()

        elif tab_key == "首页":
            self.controller.disable_bot_viz()
            self.apply_config_to_ui()

        elif tab_key == "高级设置":
            self.controller.disable_bot_viz()
            self.update_cfg_from_main_ui()
            self.apply_config_to_ui()

        elif tab_key in ("地图", "怪物", "录制", "运行日志"):
            self.controller.disable_bot_viz()
            if tab_key == "录制":
                self.record_tab.set_current_map(self.selected_map)

        else:
            logger.error(f"[UI] Unexpected tab name: {tab_name}")
            self.controller.disable_bot_viz()

        self.resize(TAB_WINDOW_SIZE[tab_key][0],
                    TAB_WINDOW_SIZE[tab_key][1])

        logger.info(f"[UI] user change tab to {tab_name}")

    def on_managed_map_selected(self, map_name):
        self.selected_map = map_name
        self.record_tab.set_current_map(map_name)
        logger.info(f"[UI] Map selected: {map_name}")

    def open_recording_for_map(self, map_name):
        self.selected_map = map_name
        self.record_tab.set_current_map(map_name)
        self.tabs.setCurrentWidget(self.tab_record)
        self.record_tab.start_continue(map_name)

    def open_rope_recording_for_map(self, map_name):
        """Switch to 录制 tab with map pre-selected for rope recording."""
        self.selected_map = map_name
        self.record_tab.set_current_map(map_name)
        self.tabs.setCurrentWidget(self.tab_record)

    def on_resources_changed(self):
        self.resource_repository.reload()
        self.data = self.resource_repository.data
        self.map_management_tab.refresh_maps(self.selected_map)
        self.monster_management_tab.refresh_monsters()

    def on_route_recording_state_changed(self, is_recording):
        if is_recording:
            self.controller.kb_listener.disable()
            self.button_start_pause.setEnabled(False)
            self.map_management_tab.setEnabled(False)
            self.monster_management_tab.setEnabled(False)
            self.button_settings.setEnabled(False)
            self.statusBar().showMessage("状态：正在录制地图路线")
        else:
            self.controller.kb_listener.enable()
            self.button_start_pause.setEnabled(True)
            self.map_management_tab.setEnabled(True)
            self.monster_management_tab.setEnabled(True)
            self.button_settings.setEnabled(True)
            self.statusBar().showMessage("状态：路线录制结束")

    def on_route_recording_finished(self, map_name):
        self.selected_map = map_name
        self.resource_repository.reload()
        self.map_management_tab.refresh_maps(map_name)
        self.record_tab.set_current_map(map_name)

    def on_map_selected(self, item):
        # Parse English name from item text
        map_name = item.text().split(" (")[0]
        self.selected_map = map_name

        map_path = os.path.join(MINIMAPS, map_name)
        self.label_map_info.setText(f"已选择地图：{map_path}")

    def on_mode_checkbox_toggle(self, toggled_checkbox):
        '''
        Mutural exclusive checkbox
        '''
        if not toggled_checkbox.isChecked():
            # Prevent unchecking — always keep one mode selected
            toggled_checkbox.setChecked(True)
            return

        if toggled_checkbox == self.checkbox_attack:
            self.checkbox_aoe_skill.blockSignals(True)
            self.checkbox_aoe_skill.setChecked(False)
            self.checkbox_aoe_skill.blockSignals(False)

        elif toggled_checkbox == self.checkbox_aoe_skill:
            self.checkbox_attack.blockSignals(True)
            self.checkbox_attack.setChecked(False)
            self.checkbox_attack.blockSignals(False)

    def toggle_auto_add_hp(self, state):
        '''
        Callback function for auto add hp checkbox
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.hp_input_widget.setVisible(enabled)
        logger.debug("[toggle_auto_add_hp] Checkbox toggled: "
                    f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_auto_add_mp(self, state):
        '''
        Callback function for auto add mp checkbox
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.mp_input_widget.setVisible(enabled)
        logger.debug("[toggle_auto_add_mp] Checkbox toggled: "
                    f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_auto_buff(self, state):
        '''
        Callback function for auto buff
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.buff_section_container.setVisible(enabled)
        logger.debug("[toggle_auto_buff] Buff section :"
                     f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_start_ui(self):
        if self.button_start_pause.isChecked(): # When start autobot
            cfg_path = "config/.config_tmp.yaml"
            try:
                self.update_cfg_from_main_ui()
                save_yaml(self.cfg, cfg_path)
                ret = self.controller.start_bot(cfg_path)
            except Exception as error:
                logger.exception(f"[toggle_start_ui] {error}")
                ret = -1

            if ret == 0: # Start success
                self.button_start_pause.setText("停止")
                self.button_start_pause.setStyleSheet(
                    "background-color: #16a34a; color: white; font-weight: 700;"
                )
                self.set_gbox_enabled(False)
                if self._debug_source_pixmap.isNull():
                    self.debug_canvas.setText("采集已就绪，正在等待首个识别画面…")
                warns = getattr(getattr(self.controller, "auto_bot", None), "startup_warnings", None) or []
                if warns:
                    tip = "\n\n".join(str(w) for w in warns)
                    QMessageBox.warning(self, "smart_patrol 警告", tip)
                    self.statusBar().showMessage("状态：已启动 — " + str(warns[0]).splitlines()[0][:80])
                else:
                    self.statusBar().showMessage("状态：运行中")
            else:
                # Start failed
                self.button_start_pause.setChecked(False)
                self._debug_source_pixmap = QPixmap()
                clear_debug_canvas(self.debug_canvas)
                self.debug_canvas.setText("启动失败，请查看运行日志")
                self.statusBar().showMessage("状态：启动失败，请查看运行日志")

        else: # When pause autobot
            self.button_start_pause.setText("开始")
            self.button_start_pause.setStyleSheet("")
            self.controller.pause_bot()
            self.set_gbox_enabled(True)
            self._debug_source_pixmap = QPixmap()
            clear_debug_canvas(self.debug_canvas) # Set debug viz to null
            self.debug_canvas.setText("启动后将在这里显示视频图层识别结果")
            clear_debug_canvas(self.route_map_canvas) # Set debug viz to null
            self.statusBar().showMessage("状态：已暂停")

    def toggle_screenshot_ui(self):
        self.controller.take_screenshot()

    def toggle_record_ui(self):
        if self.button_record.isChecked():
            self.button_record.setText("停止录制 F3")
            self.button_record.setStyleSheet("background-color: orange;")
            self.controller.start_recording()
        else:
            self.button_record.setText("录制 F3")
            self.button_record.setStyleSheet("")
            self.controller.stop_recording()


    def _force_disable_potion_profile_for_assist(self, persist=False):
        """
        Assist mode must use classic HP/MP thresholds + single key press.
        Flip potion_profile.enable off in live cfg; keep numeric settings.
        """
        hm = self.cfg.setdefault("health_monitor", {})
        profile = hm.get("potion_profile")
        if not isinstance(profile, dict):
            profile = dict(DEFAULT_POTION_PROFILE)
            hm["potion_profile"] = profile

        was_enabled = bool(profile.get("enable", False))
        profile["enable"] = False

        if was_enabled:
            logger.info(
                "[UI] Assist mode: potion_profile disabled; "
                "using classic add_hp_percent/add_mp_percent heal"
            )
            try:
                self.statusBar().showMessage(
                    "辅助模式：已关闭药品配置，改用原单次补血/蓝",
                    4000,
                )
            except Exception:
                pass

        if persist and was_enabled:
            try:
                if "config_default.yaml" not in getattr(self, "path_cfg_custom", ""):
                    self._write_current_config()
                    logger.info(
                        f"[UI] Assist mode: potion_profile.enable persisted to "
                        f"{self.path_cfg_custom}"
                    )
            except Exception as error:
                logger.warning(
                    f"[UI] Assist mode: unable to persist potion_profile disable: {error}"
                )
        return was_enabled

    def on_bot_mode_changed(self, _index=None):
        """When user selects 辅助模式, force classic heal path."""
        if getattr(self, "_suppress_bot_mode_handler", False):
            return
        mode = self.bot_mode.currentData() or "normal"
        self.cfg.setdefault("bot", {})["mode"] = mode
        if mode == "aux":
            self._force_disable_potion_profile_for_assist(persist=True)

    def open_potion_config_dialog(self):
        """Open potion profile dialog; save only on 确定."""
        hm = self.cfg.setdefault("health_monitor", {})
        current = hm.get("potion_profile")
        if not isinstance(current, dict):
            current = dict(DEFAULT_POTION_PROFILE)
        dialog = PotionConfigDialog(current, self)
        if dialog.exec() != QDialog.Accepted:
            return
        profile = dialog.get_profile()
        hm["potion_profile"] = profile
        logger.info(
            f"[UI] Potion profile saved: enable={profile.get('enable')}, "
            f"HP {profile.get('add_hp_percent_min')}-{profile.get('add_hp_percent_max')} "
            f"amt={profile.get('add_hp_potion_amount')} max={profile.get('add_hp_max')}, "
            f"MP {profile.get('add_mp_percent_min')}-{profile.get('add_mp_percent_max')} "
            f"amt={profile.get('add_mp_potion_amount')} max={profile.get('add_mp_max')}"
        )
        self.statusBar().showMessage(
            "药品配置已保存（已启用）" if profile.get("enable") else "药品配置已保存（未启用，仍用原阈值）",
            4000,
        )

    def update_cfg_from_main_ui(self):
        '''
        Collect setting from UI framework
        '''
        bot = self.cfg.setdefault("bot", {})
        bot["mode"] = self.bot_mode.currentData() or "normal"
        if bot.get("mode") == "aux":
            # Start/save in assist mode always uses classic heal (not multi-press).
            self._force_disable_potion_profile_for_assist(persist=False)

        selected_profession = self.profession_combo.currentData() or ""
        self.profession_store.apply_to_cfg(
            self.cfg, selected_profession, self.cfg_fallback
        )

        window_title = self.window_title_edit.text().strip()
        if window_title:
            self.cfg.setdefault("game_window", {})["title"] = window_title

        hm = self.cfg.setdefault("health_monitor", {})
        hm["add_hp_percent"] = self.home_hp_percent.value()
        hm["add_mp_percent"] = self.home_mp_percent.value()

        attack_type = self.cfg.setdefault("bot", {}).get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = self.cfg.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0
        hybrid_cfg = self.cfg.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0
        # Map selection
        self.cfg.setdefault("bot", {})["map"] = self.selected_map

        # Persist nametag / 名片 from home UI so save+load keep the selection.
        nametag_name = ""
        if hasattr(self, "character_name_edit"):
            nametag_name = (self.character_name_edit.text() or "").strip()
        nametag_cfg = self.cfg.setdefault("nametag", {})
        if nametag_name:
            nametag_cfg["name"] = nametag_name
            nametag_cfg["enable"] = True
            # Keep layers if already set; do not force a new default here.
            if "layers" not in nametag_cfg or nametag_cfg.get("layers") in (None, 0, ""):
                try:
                    from src.utils.nametag import load_nametag_layers
                    saved_layers = load_nametag_layers(
                        nametag_name,
                        getattr(self, "nametag_dir", None),
                        default=None,
                    )
                    if saved_layers is not None:
                        nametag_cfg["layers"] = int(saved_layers)
                except Exception:
                    pass
        elif not nametag_cfg.get("enable"):
            # Leave explicit disable alone; only clear name when UI shows empty
            # and enable is already false.
            nametag_cfg["name"] = nametag_cfg.get("name", "") or ""

        if hasattr(self, "chk_shutdown_timed"):
            self._collect_shutdown_monitor_from_ui()

    def _write_current_config(self):
        """Write current UI state as a custom-config override (diff vs default).

        Profession keybinds stay in ProfessionConfigStore. Home-page attack /
        hybrid / HP / map / mode / nametag are re-applied AFTER
        reset_profession_overrides so they are not wiped from the diff.
        """
        # SAVE_LOAD_FULL_HOME_FIX_V1
        if "config_default.yaml" in self.path_cfg_custom:
            raise ValueError("默认配置文件不可覆盖，请先加载自定义配置文件。")

        self.update_cfg_from_main_ui()
        cfg_to_save = copy.deepcopy(self.cfg)
        reset_profession_overrides(cfg_to_save, self.cfg_fallback)

        # Re-apply home UI values that reset_profession_overrides may restore
        # from fallback (directional_attack / hybrid_attack / bot.attack).
        bot = cfg_to_save.setdefault("bot", {})
        bot["mode"] = self.bot_mode.currentData() or bot.get("mode", "normal")
        bot["map"] = getattr(self, "selected_map", None) or bot.get("map", "")

        hm = cfg_to_save.setdefault("health_monitor", {})
        hm["add_hp_percent"] = self.home_hp_percent.value()
        hm["add_mp_percent"] = self.home_mp_percent.value()

        attack_type = bot.get("attack", "directional")
        section_name = "aoe_skill" if attack_type == "aoe_skill" else "directional_attack"
        section = cfg_to_save.setdefault(section_name, {})
        section["range_x"] = self.home_attack_range_x.value()
        section["range_y"] = self.home_attack_range_y.value()
        section["cooldown"] = self.home_attack_cooldown.value() / 10.0

        hybrid_cfg = cfg_to_save.setdefault("hybrid_attack", {})
        hybrid_cfg["aoe_trigger_count"] = self.home_aoe_trigger_count.value()
        hybrid_cfg["aoe_cooldown"] = self.home_aoe_cooldown.value() / 10.0

        nametag_name = ""
        if hasattr(self, "character_name_edit"):
            nametag_name = (self.character_name_edit.text() or "").strip()
        nametag_cfg = cfg_to_save.setdefault("nametag", {})
        if nametag_name:
            nametag_cfg["name"] = nametag_name
            nametag_cfg["enable"] = True
            live_layers = self.cfg.get("nametag", {}).get("layers")
            if live_layers not in (None, ""):
                nametag_cfg["layers"] = int(live_layers)

        cfg_diff = get_cfg_diff(self.cfg_base, cfg_to_save)
        save_yaml(cfg_diff, self.path_cfg_custom)
        self.profession_store.save()
        return self.path_cfg_custom

    def save_current_config(self):
        """Save the visible settings immediately from the Settings menu."""
        try:
            path = self._write_current_config()
        except Exception as error:
            logger.exception(f"[UI] Save current config failed: {error}")
            QMessageBox.warning(self, "保存失败", str(error))
            self.statusBar().showMessage("状态：配置保存失败")
            return False

        logger.info(f"[UI] Current config saved: {path}")
        self.statusBar().showMessage(f"状态：当前配置已保存到 {path}")
        QMessageBox.information(
            self,
            "保存成功",
            f"当前配置已保存到：\n{path}",
        )
        return True

    def update_debug_canvas(self, img):
        if img is None:
            return

        height, width, channels = img.shape
        qimg = QImage(
            img.data,
            width,
            height,
            width * channels,
            QImage.Format_BGR888,
        ).copy()
        self._debug_source_pixmap = QPixmap.fromImage(qimg)
        self._refresh_debug_canvas()

    def _refresh_debug_canvas(self):
        if self._debug_source_pixmap.isNull():
            return
        available = self.debug_canvas.contentsRect().size()
        available.setWidth(max(1, available.width() - 20))
        available.setHeight(max(1, available.height() - 20))
        self.debug_canvas.setPixmap(
            self._debug_source_pixmap.scaled(
                available,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_debug_source_pixmap"):
            self._refresh_debug_canvas()
        if hasattr(self, "_route_source_pixmap"):
            self._refresh_route_map_canvas()

    def update_route_map_canvas(self, img):
        if img is None:
            return

        height, width, channels = img.shape
        qimg = QImage(
            img.data,
            width,
            height,
            width * channels,
            QImage.Format_BGR888,
        ).copy()
        self._route_source_pixmap = QPixmap.fromImage(qimg)
        self.route_map_canvas.setText("")
        self._refresh_route_map_canvas()

    def _refresh_route_map_canvas(self):
        if self._route_source_pixmap.isNull():
            return
        available = self.route_map_canvas.contentsRect().size()
        available.setWidth(max(1, available.width() - 16))
        available.setHeight(max(1, available.height() - 16))
        self.route_map_canvas.setPixmap(
            self._route_source_pixmap.scaled(
                available,
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
        )

    def update_advance_setting_ui_from_cfg(self):
        '''
        Updates UI fields in an existing gbox to reflect the latest cfg[title].
        '''
        for title in self.cfg:
            if title in ADV_SETTINGS_HIDE: # skip hide settings
                continue
            # Custom/legacy config files may contain sections that were not
            # present when the advanced-settings widgets were constructed.
            gbox = self.advance_settings_gboxes.get(title)
            if gbox is None:
                continue
            refs = getattr(gbox, "_field_refs", {})
            for key, value in self.cfg[title].items():
                widget = refs.get(key)
                if widget is None:
                    continue  # unknown field, skip

                # Checkbox
                if isinstance(value, bool) and isinstance(widget, QCheckBox):
                    widget.setChecked(value)

                # List of QLineEdits
                elif isinstance(value, (list, tuple)) and isinstance(widget, list):
                    for line, v in zip(widget, value):
                        line.setText(str(v))

                # Single numeric value
                elif isinstance(value, (int, float)) and isinstance(widget, QLineEdit):
                    widget.setText(str(value))

                # Droplist
                elif isinstance(value, str) and isinstance(widget, QComboBox):
                    index = widget.findText(value)
                    if index != -1:
                        widget.setCurrentIndex(index)

                # String
                elif isinstance(value, str) and isinstance(widget, QLineEdit):
                    widget.setText(value)

    def add_buff_row(self, key="", cooldown=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)  # Tight spacing

        # Buff Key
        label_1 = QLabel("Press")
        label_1.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        key_edit = SingleKeyEdit()
        key_edit.setFixedWidth(100)
        if key:
            key_edit.set_key(key)
        key_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        row_layout.addWidget(label_1)
        row_layout.addWidget(key_edit)

        # Cooldown
        label_cd = QLabel("key, for every ")
        label_cd.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        cooldown_edit = QLineEdit()
        cooldown_edit.setPlaceholderText("0")
        cooldown_edit.setText(cooldown)
        cooldown_edit.setFixedWidth(60)
        cooldown_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        label_second = QLabel("seconds.")
        label_second.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        row_layout.addWidget(label_cd)
        row_layout.addWidget(cooldown_edit)
        row_layout.addWidget(label_second)

        # Error label (optional)
        error_label = QLabel()
        error_label.setStyleSheet("color: red;")
        error_label.setVisible(False)

        # Validation
        cooldown_edit.editingFinished.connect(
            lambda: validate_numerical_input(cooldown_edit.text(), error_label, 0, 9999))

        # Delete button
        button_delete = QPushButton("-")
        button_delete.setFixedWidth(20)
        button_delete.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button_delete.clicked.connect(lambda: self.remove_buff_row(row_widget, error_label))
        row_layout.addWidget(button_delete)

        # Align to left and fix widget height
        row_layout.setAlignment(Qt.AlignLeft)
        row_widget.setLayout(row_layout)
        row_widget.setFixedHeight(28)  # Optional: reduce vertical height

        self.buff_layout.addWidget(error_label)
        self.buff_layout.addWidget(row_widget)
        self.buff_inputs.append((key_edit, cooldown_edit))

    def remove_buff_row(self, row_widget: QWidget, error_label: QLabel):
        # Remove from layout_main
        self.buff_layout.removeWidget(row_widget)
        self.buff_layout.removeWidget(error_label)
        row_widget.setParent(None)
        error_label.setParent(None)

        # Remove from tracking list
        self.buff_inputs = [
            entry for entry in self.buff_inputs if entry[0] != row_widget
        ]

    def append_log(self, message: str, level: int):
        color = QColor("white")
        if level >= logging.ERROR:
            color = QColor("red")
        elif level >= logging.WARNING:
            color = QColor("orange")

        fmt = QTextCharFormat()
        fmt.setForeground(color)

        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n", fmt)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def closeEvent(self, event):
        '''
        Call when user close the UI window
        '''
        try:
            self._write_current_config()
        except (OSError, ValueError) as error:
            logger.error(f"[UI] Unable to save config during close: {error}")
        self.record_tab.shutdown()
        if hasattr(self, "map_management_tab"):
            self.map_management_tab.shutdown()

        # Save your UI state (e.g., last loaded config path)
        self.save_ui_state()

        # Terminate all bot threads
        self.controller.terminate_bot()

        event.accept()  # Continue with the close

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
