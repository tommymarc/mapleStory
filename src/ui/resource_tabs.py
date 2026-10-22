"""Map, monster, and route-recording management tabs."""

from argparse import Namespace
import glob
import os
import re
import shutil
import tempfile
import time
import zipfile

import cv2

from PySide6.QtCore import QThread, Qt, QUrl, QSize, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.utils.common import load_image, load_yaml, override_cfg, save_yaml
from src.utils.paths import MINIMAPS, MONSTER
from src.utils.ropes import load_ropes, ropes_path
from src.utils.patrol import load_patrol, patrol_path
from src.ui.map_manage import (
    BoundsManagePage,
    MapManageHubPage,
    RopeManagePage,
)
from src.utils.logger import logger
from src.utils.monster_import import import_monster_images
from src.utils.route_visualization import render_route_visualization


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
MONSTER_DOWNLOAD_URL = "https://maplestory.wiki/CMS/148/mob"


def bgr_to_pixmap(image):
    """Convert an OpenCV BGR image to an owning Qt pixmap."""
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        return QPixmap()
    height, width, channels = image.shape
    qimage = QImage(
        image.data,
        width,
        height,
        width * channels,
        QImage.Format_BGR888,
    ).copy()
    return QPixmap.fromImage(qimage)


def load_route_preview_pixmap(path, config_path="config/config_default.yaml"):
    """Build a display-only map/route preview for the map management page."""
    image = load_image(path)
    filename = os.path.basename(path).lower()
    map_path = os.path.join(os.path.dirname(path), "map.png")
    if filename.startswith("route") and os.path.isfile(map_path):
        base = load_image(map_path)
        cfg = load_yaml(config_path)
        route_cfg = cfg.get("route", {})
        actions = dict(route_cfg.get("color_code", {}))
        actions.update(route_cfg.get("color_code_up_down", {}))
        preview = render_route_visualization(
            base,
            image,
            actions,
            scale=4,
            crop=True,
            show_legend=True,
        )
    else:
        preview = render_route_visualization(
            image,
            scale=4,
            crop=True,
            show_legend=False,
        )
    return bgr_to_pixmap(preview)


def natural_key(path):
    parts = re.split(r"(\d+)", os.path.basename(path).lower())
    return [int(part) if part.isdigit() else part for part in parts]


def preferred_monster_preview(files):
    """Prefer the first standing animation frame for a stable preview."""
    files = list(files)
    stand_files = [
        path
        for path in files
        if re.match(
            r"^stand(?:\d+)?(?:[_-]|$)",
            os.path.splitext(os.path.basename(path))[0],
            re.IGNORECASE,
        )
    ]
    return stand_files[0] if stand_files else (files[0] if files else None)


def safe_resource_name(name):
    name = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]+", "_", name.strip()).strip("_")
    if name in ("", ".", ".."):
        raise ValueError("资源名称无效")
    return name


class ResourceRepository:
    """Filesystem-backed map/monster catalog with non-destructive config overrides."""

    def __init__(
        self,
        data_path="config/config_data.yaml",
        override_path="config/config_resource_overrides.yaml",
    ):
        self.data_path = data_path
        self.override_path = override_path
        self.reload()

    def reload(self):
        self.base_data = load_yaml(self.data_path)
        if os.path.exists(self.override_path):
            self.overrides = load_yaml(self.override_path)
        else:
            self.overrides = {}
        self.overrides.setdefault("eng_to_cn", {})
        self.overrides.setdefault("map_mobs_mapping", {})
        self.data = override_cfg(self.base_data, self.overrides)

    def save(self):
        save_yaml(self.overrides, self.override_path)
        self.reload()

    def display_name(self, name):
        return self.data.get("eng_to_cn", {}).get(name, name)

    def map_names(self):
        if not os.path.isdir(MINIMAPS):
            return []
        return sorted(
            name
            for name in os.listdir(MINIMAPS)
            if not name.startswith(".") and os.path.isdir(os.path.join(MINIMAPS, name))
        )

    def monster_names(self):
        if not os.path.isdir(MONSTER):
            return []
        return sorted(
            name
            for name in os.listdir(MONSTER)
            if not name.startswith(".")
            and os.path.isdir(os.path.join(MONSTER, name))
            and self.monster_files(name)
        )

    def map_files(self, map_name):
        map_dir = os.path.join(MINIMAPS, map_name)
        files = []
        map_path = os.path.join(map_dir, "map.png")
        if os.path.isfile(map_path):
            files.append(map_path)
        files.extend(sorted(glob.glob(os.path.join(map_dir, "route*.png")), key=natural_key))
        return files

    def route_files(self, map_name):
        map_dir = os.path.join(MINIMAPS, map_name)
        return sorted(glob.glob(os.path.join(map_dir, "route*.png")), key=natural_key)

    def monster_files(self, monster_name):
        monster_dir = os.path.join(MONSTER, monster_name)
        files = glob.glob(os.path.join(monster_dir, "*"))
        return sorted(
            [path for path in files if os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS],
            key=natural_key,
        )

    def map_monsters(self, map_name):
        return list(self.data.get("map_mobs_mapping", {}).get(map_name, ()))

    def register_map(self, map_name, display_name=None):
        self.overrides["eng_to_cn"][map_name] = display_name or map_name
        self.overrides["map_mobs_mapping"].setdefault(map_name, [])
        self.save()

    def set_map_monsters(self, map_name, monster_names):
        self.overrides["map_mobs_mapping"][map_name] = list(monster_names)
        self.save()

    def delete_map(self, map_name):
        map_dir = os.path.join(MINIMAPS, map_name)
        if os.path.isdir(map_dir):
            shutil.rmtree(map_dir)
        self.overrides["map_mobs_mapping"].pop(map_name, None)
        self.overrides["eng_to_cn"].pop(map_name, None)
        self.save()

    def delete_route(self, route_path):
        # Never delete map.png — only route*.png.
        base = os.path.basename(route_path).lower()
        if base == "map.png":
            raise ValueError("拒绝删除 map.png；请只删除 route*.png")
        if not re.match(r"route.*\.png$", base):
            raise ValueError(f"拒绝删除非路线文件：{base}")
        if os.path.isfile(route_path):
            os.remove(route_path)

    def delete_monster(self, monster_name):
        monster_dir = os.path.join(MONSTER, monster_name)
        if os.path.isdir(monster_dir):
            shutil.rmtree(monster_dir)
        self.overrides["eng_to_cn"].pop(monster_name, None)
        for map_name in self.map_names():
            monsters = [name for name in self.map_monsters(map_name) if name != monster_name]
            self.overrides["map_mobs_mapping"][map_name] = monsters
        self.save()

    def import_monster(self, monster_name, source_paths):
        monster_name = safe_resource_name(monster_name)
        target_dir = os.path.join(MONSTER, monster_name)
        result = import_monster_images(source_paths, target_dir)

        if result.skipped_death_frames:
            logger.info(
                f"Skipped {result.skipped_death_frames} death animation frame(s) "
                f"while importing monster '{monster_name}'"
            )

        self.overrides["eng_to_cn"][monster_name] = monster_name
        self.save()
        return monster_name

    def import_routes(self, map_name, source_path):
        target_dir = os.path.join(MINIMAPS, map_name)
        if not os.path.isdir(target_dir):
            raise FileNotFoundError(f"地图目录不存在：{target_dir}")

        route_sources = []
        with tempfile.TemporaryDirectory() as temp_dir:
            if os.path.isdir(source_path):
                route_sources = glob.glob(os.path.join(source_path, "route*.png"))
            elif source_path.lower().endswith(".zip"):
                with zipfile.ZipFile(source_path) as archive:
                    for info in archive.infolist():
                        filename = os.path.basename(info.filename)
                        if info.is_dir() or not re.match(r"route.*\.png$", filename, re.IGNORECASE):
                            continue
                        extracted_path = os.path.join(temp_dir, filename)
                        with archive.open(info) as source, open(extracted_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                        route_sources.append(extracted_path)
            else:
                raise ValueError("仅支持路线目录或 ZIP 压缩包")

            route_sources = sorted(route_sources, key=natural_key)
            if not route_sources:
                raise ValueError("没有找到 route*.png 路线文件")

            next_index = self.max_route_index(map_name) + 1
            imported = []
            for source in route_sources:
                target = os.path.join(target_dir, f"route{next_index}.png")
                shutil.copy2(source, target)
                imported.append(target)
                next_index += 1
            return imported

    def import_map_package(self, map_name, source_path):
        map_name = safe_resource_name(map_name)
        target_dir = os.path.join(MINIMAPS, map_name)
        if os.path.exists(target_dir):
            raise FileExistsError(f"地图“{map_name}”已经存在")
        os.makedirs(target_dir)
        try:
            if os.path.isdir(source_path):
                for source in glob.glob(os.path.join(source_path, "*")):
                    filename = os.path.basename(source)
                    if os.path.isfile(source) and os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS:
                        shutil.copy2(source, os.path.join(target_dir, filename))
            elif source_path.lower().endswith(".zip"):
                with zipfile.ZipFile(source_path) as archive:
                    for info in archive.infolist():
                        filename = os.path.basename(info.filename)
                        if info.is_dir() or os.path.splitext(filename)[1].lower() not in IMAGE_EXTENSIONS:
                            continue
                        with archive.open(info) as source, open(
                            os.path.join(target_dir, filename), "wb"
                        ) as target:
                            shutil.copyfileobj(source, target)
            else:
                raise ValueError("仅支持地图目录或 ZIP 压缩包")

            if not os.path.isfile(os.path.join(target_dir, "map.png")):
                raise ValueError("地图包中缺少 map.png")
            if not glob.glob(os.path.join(target_dir, "route*.png")):
                raise ValueError("地图包中缺少 route*.png")
        except Exception:
            shutil.rmtree(target_dir)
            raise
        self.register_map(map_name)
        return map_name

    def max_route_index(self, map_name):
        max_index = 0
        for path in self.route_files(map_name):
            match = re.search(r"route_?(\d+)", os.path.basename(path), re.IGNORECASE)
            if match:
                max_index = max(max_index, int(match.group(1)))
        return max_index


class ImageCarousel(QWidget):
    """Small reusable image preview with previous/next controls."""

    def __init__(self, empty_text, pixmap_loader=None, parent=None):
        super().__init__(parent)
        self.empty_text = empty_text
        self.pixmap_loader = pixmap_loader
        self.files = []
        self.index = 0
        self._source_pixmap = QPixmap()
        self._caption_text = "未找到图片"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        self.preview = QLabel(empty_text)
        self.preview.setObjectName("imagePreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(0, 220)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet(
            "QLabel#imagePreview {"
            "background-color: #f8fafc; color: #8290a4; "
            "border: 1px solid #d8e1ed; border-radius: 12px; padding: 10px;"
            "}"
        )
        layout.addWidget(self.preview, 1)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.previous_button = QPushButton("‹")
        self.previous_button.setObjectName("carouselButton")
        self.previous_button.setFixedSize(38, 34)
        self.previous_button.clicked.connect(self.previous)
        self.caption = QLabel("未找到图片")
        self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setMinimumWidth(0)
        self.caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.counter = QLabel("0 / 0")
        self.counter.setMinimumWidth(52)
        self.counter.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("carouselButton")
        self.next_button.setFixedSize(38, 34)
        self.next_button.clicked.connect(self.next)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.caption, 1)
        controls.addWidget(self.counter)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)
        self._refresh()

    def set_files(self, files, selected_path=None):
        self.files = list(files)
        self.index = 0
        if selected_path in self.files:
            self.index = self.files.index(selected_path)
        self._refresh()

    def current_path(self):
        return self.files[self.index] if self.files else ""

    def previous(self):
        if self.files:
            self.index = (self.index - 1) % len(self.files)
            self._refresh()

    def next(self):
        if self.files:
            self.index = (self.index + 1) % len(self.files)
            self._refresh()

    def _refresh(self):
        has_files = bool(self.files)
        self.previous_button.setEnabled(len(self.files) > 1)
        self.next_button.setEnabled(len(self.files) > 1)
        if not has_files:
            self._source_pixmap = QPixmap()
            self.preview.setPixmap(QPixmap())
            self.preview.setText(self.empty_text)
            self._set_caption("未找到图片")
            self.counter.setText("0 / 0")
            return

        path = self.files[self.index]
        try:
            pixmap = self.pixmap_loader(path) if self.pixmap_loader else QPixmap(path)
        except Exception as error:
            logger.warning(f"Failed to render image preview '{path}': {error}")
            pixmap = QPixmap(path)
        if pixmap.isNull():
            self._source_pixmap = QPixmap()
            self.preview.setPixmap(QPixmap())
            self.preview.setText("图片读取失败")
        else:
            self.preview.setText("")
            self._source_pixmap = pixmap
            self._update_preview_pixmap()
        self._set_caption(os.path.basename(path))
        self.counter.setText(f"{self.index + 1} / {len(self.files)}")

    def _set_caption(self, text):
        self._caption_text = text
        self.caption.setToolTip(text)
        self._update_caption()

    def _update_caption(self):
        available_width = max(40, self.caption.width() - 8)
        elided = self.caption.fontMetrics().elidedText(
            self._caption_text,
            Qt.ElideMiddle,
            available_width,
        )
        self.caption.setText(elided)

    def _update_preview_pixmap(self):
        if self._source_pixmap.isNull():
            return
        available = self.preview.contentsRect().size()
        available.setWidth(max(1, available.width() - 20))
        available.setHeight(max(1, available.height() - 20))
        self.preview.setPixmap(
            self._source_pixmap.scaled(
                available,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview_pixmap()
        self._update_caption()


class MapManagementTab(QWidget):
    map_selected = Signal(str)
    record_requested = Signal(str)
    resources_changed = Signal()
    recording_state_changed = Signal(bool)
    manage_capture_state_changed = Signal(bool)

    def __init__(
        self,
        repository,
        parent=None,
        config_path_provider=None,
        bot_running_provider=None,
        stop_bot_callback=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.config_path_provider = config_path_provider
        self.bot_running_provider = bot_running_provider
        self.stop_bot_callback = stop_bot_callback
        self.current_map = ""
        self._monster_back_to_hub = False
        self._route_back_to_hub = False
        self.stack = QStackedWidget()
        self.main_page = self._build_main_page()
        self.route_page = self._build_route_page()
        self.monster_page = self._build_monster_page()
        self.manage_hub = MapManageHubPage()
        self.rope_manage = RopeManagePage(
            repository,
            config_path_provider=config_path_provider,
            bot_running_provider=bot_running_provider,
            stop_bot_callback=stop_bot_callback,
        )
        self.bounds_manage = BoundsManagePage(
            repository,
            config_path_provider=config_path_provider,
            bot_running_provider=bot_running_provider,
            stop_bot_callback=stop_bot_callback,
        )
        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.route_page)
        self.stack.addWidget(self.monster_page)
        self.stack.addWidget(self.manage_hub)
        self.stack.addWidget(self.rope_manage)
        self.stack.addWidget(self.bounds_manage)
        self.manage_hub.back_requested.connect(lambda: self.stack.setCurrentWidget(self.main_page))
        self.manage_hub.open_ropes.connect(self._open_rope_manage)
        self.manage_hub.open_bounds.connect(self._open_bounds_manage)
        self.manage_hub.open_monsters.connect(self._show_monster_selector_from_manage)
        self.manage_hub.open_routes.connect(self._show_route_editor_from_manage)
        self.rope_manage.back_requested.connect(self._open_manage_hub)
        self.rope_manage.resources_changed.connect(self.resources_changed.emit)
        self.rope_manage.recording_state_changed.connect(self._on_manage_capture_state)
        self.bounds_manage.back_requested.connect(self._open_manage_hub)
        self.bounds_manage.resources_changed.connect(self.resources_changed.emit)
        self.bounds_manage.recording_state_changed.connect(self._on_manage_capture_state)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        self.refresh_maps()

    def _build_main_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.carousel = ImageCarousel(
            "暂无地图图片",
            pixmap_loader=load_route_preview_pixmap,
        )
        layout.addWidget(self.carousel, 1)

        header = QHBoxLayout()
        header.addWidget(QLabel("地图列表"))
        header.addStretch(1)
        import_button = QPushButton("导入路线")
        import_button.clicked.connect(self._import_routes)
        header.addWidget(import_button)
        layout.addLayout(header)

        self.map_list = QListWidget()
        self.map_list.setObjectName("mapList")
        # Custom item widgets need zero ::item padding; global stylesheet padding
        # would shrink the widget rect and clip label/button glyphs mid-height.
        self.map_list.setStyleSheet(
            """
            QListWidget#mapList::item {
                min-height: 44px;
                padding: 0px;
                margin: 2px 0;
                border-radius: 7px;
            }
            QListWidget#mapList::item:hover {
                background-color: #f0efff;
            }
            QListWidget#mapList::item:selected {
                background-color: #6657d9;
            }
            """
        )
        self.map_list.currentItemChanged.connect(self._on_map_changed)
        layout.addWidget(self.map_list, 1)

        actions = QHBoxLayout()
        delete_button = QPushButton("删除地图")
        delete_button.setObjectName("dangerOutlineButton")
        delete_button.clicked.connect(self._delete_map)
        actions.addStretch(1)
        actions.addWidget(delete_button)
        layout.addLayout(actions)
        return page

    def _build_route_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QHBoxLayout()
        back = QPushButton("← 返回")
        back.clicked.connect(self._back_from_route_page)
        self.route_title = QLabel("路线")
        header.addWidget(back)
        header.addWidget(self.route_title)
        header.addStretch(1)
        record_button = QPushButton("录制路线")
        record_button.setObjectName("secondaryActionButton")
        record_button.clicked.connect(self._request_record)
        header.addWidget(record_button)
        layout.addLayout(header)
        self.route_list = QListWidget()
        layout.addWidget(self.route_list, 1)
        actions = QHBoxLayout()
        open_btn = QPushButton("打开地图文件夹")
        open_btn.clicked.connect(self._open_map_folder)
        delete_button = QPushButton("删除选中路线")
        delete_button.setObjectName("dangerOutlineButton")
        delete_button.clicked.connect(self._delete_route)
        actions.addWidget(open_btn)
        actions.addStretch(1)
        actions.addWidget(delete_button)
        layout.addLayout(actions)
        return page

    def _build_monster_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QHBoxLayout()
        back = QPushButton("← 返回")
        back.clicked.connect(self._back_from_monster_page)
        self.monster_title = QLabel("选择怪物")
        header.addWidget(back)
        header.addWidget(self.monster_title)
        header.addStretch(1)
        layout.addLayout(header)
        self.monster_check_list = QListWidget()
        layout.addWidget(self.monster_check_list, 1)
        save_button = QPushButton("保存怪物列表")
        save_button.setObjectName("secondaryActionButton")
        save_button.clicked.connect(self._save_monster_selection)
        layout.addWidget(save_button, alignment=Qt.AlignRight)
        return page

    def refresh_maps(self, selected_name=None):
        self.repository.reload()
        selected_name = selected_name or self.current_map
        self.map_list.blockSignals(True)
        self.map_list.clear()
        selected_item = None
        for name in self.repository.map_names():
            monsters = [self.repository.display_name(item) for item in self.repository.map_monsters(name)]
            suffix = f" [{', '.join(monsters)}]" if monsters else ""
            item = QListWidgetItem()
            item.setData(Qt.UserRole, name)
            row = QWidget()
            row.setMinimumHeight(44)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(8)
            row_layout.setAlignment(Qt.AlignVCenter)
            label = QLabel(f"🗺 {self.repository.display_name(name)}{suffix}")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label.setStyleSheet("color: #1e293b; background: transparent;")
            manage_btn = QPushButton("管理")
            manage_btn.setFixedSize(72, 30)
            manage_btn.setStyleSheet(
                "min-height: 0; padding: 4px 10px; font-weight: 600;"
            )
            manage_btn.clicked.connect(lambda _checked=False, n=name: self._open_manage(n))
            row_layout.addWidget(label, 1)
            row_layout.addWidget(manage_btn, 0, Qt.AlignVCenter)
            hint = row.sizeHint()
            item.setSizeHint(QSize(max(hint.width(), 120), max(44, hint.height())))
            self.map_list.addItem(item)
            self.map_list.setItemWidget(item, row)
            if name == selected_name:
                selected_item = item
        self.map_list.blockSignals(False)
        if selected_item:
            self.map_list.setCurrentItem(selected_item)
        elif self.map_list.count():
            self.map_list.setCurrentRow(0)
        else:
            self.current_map = ""
            self.carousel.set_files([])
            self.map_selected.emit("")

    def select_map(self, map_name):
        for index in range(self.map_list.count()):
            item = self.map_list.item(index)
            if item.data(Qt.UserRole) == map_name:
                self.map_list.setCurrentItem(item)
                return True
        return False

    def _on_map_changed(self, current, _previous):
        if current is None:
            return
        # Keep custom-row label readable against selection background.
        for index in range(self.map_list.count()):
            item = self.map_list.item(index)
            widget = self.map_list.itemWidget(item)
            if widget is None:
                continue
            label = widget.findChild(QLabel)
            if label is None:
                continue
            if item is current:
                label.setStyleSheet("color: #ffffff; background: transparent;")
            else:
                label.setStyleSheet("color: #1e293b; background: transparent;")
        self.current_map = current.data(Qt.UserRole)
        self.carousel.set_files(self.repository.map_files(self.current_map))
        self.map_selected.emit(self.current_map)


    def _hub_summary(self, map_name):
        import os as _os
        ropes = load_ropes(map_name)
        n_edges = len(ropes.get("edges") or [])
        n_routes = len(self.repository.route_files(map_name))
        n_mobs = len(self.repository.map_monsters(map_name))
        patrol = load_patrol(map_name)
        has_patrol = _os.path.isfile(patrol_path(map_name))
        return (
            f"地图 id：{map_name}\n"
            f"绳子边：{n_edges}　路线：{n_routes}　怪物：{n_mobs}\n"
            f"边界文件：{'已有 patrol.yaml' if has_patrol else '未建（将用全局 smart_patrol）'} "
            f"range={patrol.get('range')}"
        )

    def _open_manage(self, map_name):
        self.current_map = map_name
        self.select_map(map_name)
        self._open_manage_hub()

    def _open_manage_hub(self):
        if not self.current_map:
            return
        self.manage_hub.set_map(
            self.current_map,
            self.repository.display_name(self.current_map),
            self._hub_summary(self.current_map),
        )
        self.stack.setCurrentWidget(self.manage_hub)

    def _open_rope_manage(self):
        if not self.current_map:
            return
        self.rope_manage.set_map(self.current_map)
        self.stack.setCurrentWidget(self.rope_manage)

    def _open_bounds_manage(self):
        if not self.current_map:
            return
        self.bounds_manage.set_map(self.current_map)
        self.stack.setCurrentWidget(self.bounds_manage)

    def _show_monster_selector_from_manage(self):
        self._monster_back_to_hub = True
        self._show_monster_selector()

    def _show_route_editor_from_manage(self):
        self._route_back_to_hub = True
        self._show_route_editor()

    def _back_from_monster_page(self):
        if getattr(self, "_monster_back_to_hub", False):
            self._monster_back_to_hub = False
            self._open_manage_hub()
        else:
            self.stack.setCurrentWidget(self.main_page)

    def _back_from_route_page(self):
        if getattr(self, "_route_back_to_hub", False):
            self._route_back_to_hub = False
            self._open_manage_hub()
        else:
            self.stack.setCurrentWidget(self.main_page)

    def _open_map_folder(self):
        if not self.current_map:
            return
        from src.utils.paths import minimap_dir

        folder = os.path.abspath(minimap_dir(self.current_map))
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def shutdown(self):
        if hasattr(self, "bounds_manage"):
            self.bounds_manage.shutdown()
        if hasattr(self, "rope_manage"):
            self.rope_manage.shutdown()

    def _on_manage_capture_state(self, is_recording: bool):
        """In-place rope/bounds capture on manage pages — keep this tab enabled."""
        self.manage_capture_state_changed.emit(bool(is_recording))

    def _request_record(self):
        if not self.current_map:
            QMessageBox.warning(self, "录制路线", "请先选择地图。")
            return
        self.record_requested.emit(self.current_map)

    def _show_route_editor(self):
        if not self.current_map:
            return
        self.route_title.setText(f"路线 · {self.repository.display_name(self.current_map)}")
        self._refresh_route_list()
        self.stack.setCurrentWidget(self.route_page)

    def _refresh_route_list(self):
        self.route_list.clear()
        for path in self.repository.route_files(self.current_map):
            item = QListWidgetItem(f"🗺 {os.path.splitext(os.path.basename(path))[0]}")
            item.setData(Qt.UserRole, path)
            self.route_list.addItem(item)

    def _delete_route(self):
        item = self.route_list.currentItem()
        if item is None:
            return
        route_path = item.data(Qt.UserRole)
        base = os.path.basename(route_path or "")
        if base.lower() == "map.png":
            QMessageBox.warning(self, "删除路线", "不能删除 map.png。")
            return
        if QMessageBox.question(
            self, "删除路线", f"确定删除 {base} 吗？\n不会删除 map.png。"
        ) != QMessageBox.Yes:
            return
        try:
            self.repository.delete_route(route_path)
        except ValueError as err:
            QMessageBox.warning(self, "删除路线", str(err))
            return
        self._refresh_route_list()
        self.carousel.set_files(self.repository.map_files(self.current_map))
        self.resources_changed.emit()

    def _show_monster_selector(self):
        if not self.current_map:
            return
        self.monster_title.setText(f"怪物 · {self.repository.display_name(self.current_map)}")
        selected = set(self.repository.map_monsters(self.current_map))
        self.monster_check_list.clear()
        for name in self.repository.monster_names():
            item = QListWidgetItem(f"👾 {self.repository.display_name(name)}")
            item.setData(Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in selected else Qt.Unchecked)
            self.monster_check_list.addItem(item)
        self.stack.setCurrentWidget(self.monster_page)

    def _save_monster_selection(self):
        selected = []
        for index in range(self.monster_check_list.count()):
            item = self.monster_check_list.item(index)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        self.repository.set_map_monsters(self.current_map, selected)
        self.refresh_maps(self.current_map)
        if getattr(self, "_monster_back_to_hub", False):
            self._monster_back_to_hub = False
            self._open_manage_hub()
        else:
            self.stack.setCurrentWidget(self.main_page)
        self.resources_changed.emit()

    def _delete_map(self):
        if not self.current_map:
            return
        display_name = self.repository.display_name(self.current_map)
        if QMessageBox.question(
            self,
            "删除地图",
            f"确定删除地图“{display_name}”、map.png 和全部路线吗？",
        ) != QMessageBox.Yes:
            return
        self.repository.delete_map(self.current_map)
        self.current_map = ""
        self.refresh_maps()
        self.resources_changed.emit()

    def _import_routes(self):
        source_type, accepted = QInputDialog.getItem(
            self,
            "导入路线",
            "请选择导入方式：",
            [
                "路线目录 → 当前地图",
                "路线 ZIP → 当前地图",
                "完整地图目录",
                "完整地图 ZIP",
            ],
            editable=False,
        )
        if not accepted:
            return

        is_full_map = source_type.startswith("完整地图")
        if not is_full_map and not self.current_map:
            QMessageBox.warning(self, "导入路线", "请先选择目标地图。")
            return

        if source_type in ("路线目录 → 当前地图", "完整地图目录"):
            source = QFileDialog.getExistingDirectory(self, "选择地图或路线目录")
        else:
            source, _ = QFileDialog.getOpenFileName(self, "选择 ZIP", "", "ZIP (*.zip)")
        if not source:
            return

        if is_full_map:
            default_name = os.path.splitext(os.path.basename(source.rstrip(os.sep)))[0]
            map_name, accepted = QInputDialog.getText(
                self,
                "导入完整地图",
                "请输入导入后的地图名称：",
                text=default_name,
            )
            if not accepted or not map_name.strip():
                return
            try:
                imported_name = self.repository.import_map_package(map_name, source)
            except Exception as error:
                QMessageBox.warning(self, "导入失败", str(error))
                return
            self.refresh_maps(imported_name)
            self.resources_changed.emit()
            QMessageBox.information(self, "导入成功", f"地图“{imported_name}”导入成功。")
            return

        try:
            imported = self.repository.import_routes(self.current_map, source)
        except Exception as error:
            QMessageBox.warning(self, "导入失败", str(error))
            return
        self.carousel.set_files(self.repository.map_files(self.current_map), imported[0])
        QMessageBox.information(self, "导入成功", f"已导入 {len(imported)} 条路线。")
        self.resources_changed.emit()


class MonsterManagementTab(QWidget):
    resources_changed = Signal()

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.current_monster = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("怪物素材管理")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("选择怪物查看模板图片，也可以导入或删除怪物素材。")
        subtitle.setStyleSheet("color: #718096;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        list_panel = QWidget()
        list_panel.setMinimumWidth(260)
        list_panel.setMaximumWidth(380)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 10, 0)
        list_layout.setSpacing(10)

        header = QHBoxLayout()
        list_label = QLabel("怪物列表")
        list_label.setStyleSheet("font-weight: 700; color: #334155;")
        header.addWidget(list_label)
        header.addStretch(1)
        download = QPushButton("下载")
        download.setToolTip("打开怪物素材下载页面")
        download.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(MONSTER_DOWNLOAD_URL))
        )
        import_button = QPushButton("导入")
        import_button.setObjectName("secondaryActionButton")
        import_button.clicked.connect(self._import_monster)
        header.addWidget(download)
        header.addWidget(import_button)
        list_layout.addLayout(header)

        self.monster_list = QListWidget()
        self.monster_list.currentItemChanged.connect(self._on_monster_changed)
        list_layout.addWidget(self.monster_list, 1)
        delete_button = QPushButton("删除怪物")
        delete_button.setObjectName("dangerOutlineButton")
        delete_button.clicked.connect(self._delete_monster)
        list_layout.addWidget(delete_button)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(10, 0, 0, 0)
        preview_layout.setSpacing(10)
        preview_label = QLabel("图片预览")
        preview_label.setStyleSheet("font-weight: 700; color: #334155;")
        preview_layout.addWidget(preview_label)
        self.carousel = ImageCarousel("暂无怪物图片")
        preview_layout.addWidget(self.carousel, 1)

        splitter.addWidget(list_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 700])
        layout.addWidget(splitter, 1)
        self.refresh_monsters()

    def refresh_monsters(self, selected_name=None):
        self.repository.reload()
        selected_name = selected_name or self.current_monster
        self.monster_list.blockSignals(True)
        self.monster_list.clear()
        selected_item = None
        for name in self.repository.monster_names():
            item = QListWidgetItem(f"👾 {self.repository.display_name(name)}")
            item.setData(Qt.UserRole, name)
            self.monster_list.addItem(item)
            if name == selected_name:
                selected_item = item
        self.monster_list.blockSignals(False)
        if selected_item:
            self.monster_list.setCurrentItem(selected_item)
        elif self.monster_list.count():
            self.monster_list.setCurrentRow(0)
        else:
            self.current_monster = ""
            self.carousel.set_files([])

    def _on_monster_changed(self, current, _previous):
        if current is None:
            return
        self.current_monster = current.data(Qt.UserRole)
        files = self.repository.monster_files(self.current_monster)
        self.carousel.set_files(files, preferred_monster_preview(files))

    def _import_monster(self):
        name, accepted = QInputDialog.getText(self, "导入怪物", "请输入怪物名称：")
        if not accepted or not name.strip():
            return
        try:
            safe_name = safe_resource_name(name)
        except ValueError as error:
            QMessageBox.warning(self, "导入失败", str(error))
            return
        target_dir = os.path.join(MONSTER, safe_name)
        if os.path.isdir(target_dir) and os.listdir(target_dir):
            if QMessageBox.question(
                self,
                "怪物已存在",
                f"“{safe_name}”已经存在，是否追加导入图片？",
            ) != QMessageBox.Yes:
                return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择怪物图片或 ZIP",
            "",
            "怪物素材 (*.png *.jpg *.jpeg *.bmp *.zip);;所有文件 (*)",
        )
        if not paths:
            return
        try:
            imported_name = self.repository.import_monster(safe_name, paths)
        except Exception as error:
            QMessageBox.warning(self, "导入失败", str(error))
            return
        self.refresh_monsters(imported_name)
        self.resources_changed.emit()
        QMessageBox.information(self, "导入成功", f"怪物“{imported_name}”导入成功。")

    def _delete_monster(self):
        if not self.current_monster:
            return
        display_name = self.repository.display_name(self.current_monster)
        if QMessageBox.question(
            self,
            "删除怪物",
            f"确定删除怪物“{display_name}”及其全部图片，并解除地图关联吗？",
        ) != QMessageBox.Yes:
            return
        self.repository.delete_monster(self.current_monster)
        self.current_monster = ""
        self.refresh_monsters()
        self.resources_changed.emit()


class RouteRecorderWorker(QThread):
    frame_ready = Signal(object)
    status_changed = Signal(str)
    recording_started = Signal(str)
    recording_finished = Signal(str)
    failed = Signal(str)

    def __init__(self, map_name, continue_existing=False, config_path="", parent=None):
        super().__init__(parent)
        self.map_name = map_name
        self.continue_existing = continue_existing
        self.config_path = config_path
        self.recorder = None
        self._last_preview_emit = 0.0
        self._last_status = ""

    @staticmethod
    def _bounded_preview(image, max_width=1280, max_height=720):
        """Limit queued preview frames so the UI thread cannot be flooded."""
        height, width = image.shape[:2]
        scale = min(max_width / width, max_height / height, 1.0)
        if scale < 1.0:
            return cv2.resize(
                image,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return image.copy()

    def _cleanup_incomplete_map(self):
        if self.continue_existing:
            return
        map_dir = os.path.join(MINIMAPS, self.map_name)
        map_path = os.path.join(map_dir, "map.png")
        if os.path.isdir(map_dir) and not os.path.isfile(map_path):
            shutil.rmtree(map_dir)
            logger.info(f"Removed incomplete map directory: {map_dir}")

    def run(self):
        try:
            from tools.routeRecorder import RouteRecorder

            map_path = os.path.join(MINIMAPS, self.map_name, "map.png")
            args = Namespace(
                new_map=self.map_name,
                cfg="custom",
                map=map_path if self.continue_existing else "",
                ui_mode=True,
                continue_existing=self.continue_existing,
                config_path=self.config_path,
            )
            self.recorder = RouteRecorder(args)
            self.recording_started.emit(self.map_name)

            while not self.isInterruptionRequested() and not self.recorder.is_terminated:
                started_at = time.time()
                self.recorder.run_once()
                now = time.monotonic()
                if self.recorder.img_route is not None and now - self._last_preview_emit >= 0.2:
                    viewport = None
                    if self.recorder.img_minimap is not None:
                        viewport = (
                            self.recorder.loc_minimap_global[0],
                            self.recorder.loc_minimap_global[1],
                            self.recorder.img_minimap.shape[1],
                            self.recorder.img_minimap.shape[0],
                        )
                    preview = render_route_visualization(
                        self.recorder.img_map,
                        self.recorder.img_route,
                        self.recorder.color_code,
                        player_position=self.recorder.loc_player_global,
                        viewport=viewport,
                        scale=self.recorder.cfg["minimap"]["debug_window_upscale"],
                        crop=True,
                        show_legend=True,
                    )
                    self.frame_ready.emit(self._bounded_preview(preview))
                    self._last_preview_emit = now
                if self.recorder.last_status != self._last_status:
                    self._last_status = self.recorder.last_status
                    self.status_changed.emit(self._last_status)
                elapsed = time.time() - started_at
                remaining_ms = int(max(0, 1.0 / self.recorder.fps_limit - elapsed) * 1000)
                if remaining_ms:
                    self.msleep(remaining_ms)

            if self.recorder is not None and not self.recorder.is_terminated:
                self.recorder.stop()
            self._cleanup_incomplete_map()
            self.status_changed.emit("录制结束")
            self.recording_finished.emit(self.map_name)
        except Exception as error:
            logger.exception(f"[RouteRecorderWorker] {error}")
            if self.recorder is not None:
                try:
                    self.recorder.stop()
                except Exception as stop_error:
                    logger.error(f"[RouteRecorderWorker] Stop failed: {stop_error}")
            self._cleanup_incomplete_map()
            self.failed.emit(str(error))

    def stop_recording(self):
        if self.recorder is not None:
            self.recorder.request_stop()
        else:
            self.requestInterruption()




class RecordTab(QWidget):
    recording_state_changed = Signal(bool)
    recording_finished = Signal(str)

    def __init__(self, repository, config_path_provider=None, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.config_path_provider = config_path_provider
        self.current_map = ""
        self.worker = None
        self._preview_pixmap = QPixmap()

        layout = QVBoxLayout(self)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("路线录制"))
        status_row.addStretch(1)
        self.status_label = QLabel("尚未开始")
        status_row.addWidget(self.status_label)
        layout.addLayout(status_row)

        self.preview = QLabel("开始录制后将在这里显示 RouteMap")
        self.preview.setObjectName("routeRecordPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(0, 200)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.preview.setStyleSheet(
            "QLabel#routeRecordPreview {"
            "background-color: #f8fafc; color: #8290a4; "
            "border: 1px solid #d8e1ed; border-radius: 12px; padding: 10px;"
            "}"
        )
        layout.addWidget(self.preview, 1)

        instructions = QGroupBox()
        instruction_layout = QVBoxLayout(instructions)
        instruction_layout.addWidget(QLabel(
            "F1  暂停 / 继续录制\n"
            "F2  保存当前路线\n"
            "F3  清除当前未保存路线\n"
            "F4  停止路线录制"
        ))
        layout.addWidget(instructions)

        self.new_button = QPushButton("录制新地图")
        self.new_button.setObjectName("secondaryActionButton")
        self.new_button.setMinimumHeight(44)
        self.new_button.clicked.connect(self._new_or_stop)
        self.continue_button = QPushButton("继续录制当前地图")
        self.continue_button.setMinimumHeight(44)
        self.continue_button.clicked.connect(self._continue_current_map)
        layout.addWidget(self.new_button)
        layout.addWidget(self.continue_button)


    def set_current_map(self, map_name):
        self.current_map = map_name

    def start_continue(self, map_name):
        self.set_current_map(map_name)
        self._continue_current_map()

    def _new_or_stop(self):
        if self.worker is not None and self.worker.isRunning():
            self._stop()
            return
        name, accepted = QInputDialog.getText(self, "录制地图路线", "请输入新建地图名称：")
        if not accepted or not name.strip():
            return
        try:
            map_name = safe_resource_name(name)
        except ValueError as error:
            QMessageBox.warning(self, "录制新地图", str(error))
            return
        map_dir = os.path.join(MINIMAPS, map_name)
        if os.path.exists(map_dir):
            map_path = os.path.join(map_dir, "map.png")
            if os.path.isfile(map_path):
                QMessageBox.warning(self, "录制新地图", "该地图已经存在，请使用继续录制。")
                return
            if QMessageBox.question(
                self,
                "发现未完成录制",
                "检测到上次失败留下的同名目录，尚未生成地图。是否清理后重新录制？",
            ) != QMessageBox.Yes:
                return
            shutil.rmtree(map_dir)
        self._start(map_name, continue_existing=False)

    def _continue_current_map(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.current_map:
            QMessageBox.warning(self, "继续录制路线", "请先在地图 Tab 选择地图。")
            return
        if QMessageBox.question(
            self,
            "继续录制路线",
            "当前选中的地图是"
            f"“{self.repository.display_name(self.current_map)}”，确定继续录制吗？",
        ) != QMessageBox.Yes:
            return
        self._start(self.current_map, continue_existing=True)

    def _start(self, map_name, continue_existing):
        self.current_map = map_name
        config_path = self.config_path_provider() if self.config_path_provider else ""
        self.worker = RouteRecorderWorker(
            map_name,
            continue_existing,
            config_path=config_path,
            parent=self,
        )
        self.worker.frame_ready.connect(self._update_preview)
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.recording_started.connect(self._on_started)
        self.worker.recording_finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.status_label.setText(f"正在启动：{map_name}")
        self.new_button.setText("停止录制")
        self.continue_button.setEnabled(False)
        self.recording_state_changed.emit(True)
        self.worker.start()

    def _stop(self):
        if self.worker is not None:
            self.status_label.setText("正在停止录制…")
            self.new_button.setEnabled(False)
            self.worker.stop_recording()

    def _on_started(self, map_name):
        self.status_label.setText(f"正在录制：{map_name}")

    def _on_finished(self, map_name):
        if os.path.isfile(os.path.join(MINIMAPS, map_name, "map.png")):
            self.repository.register_map(map_name)
            self.status_label.setText("录制结束")
        else:
            self.status_label.setText("录制已停止，未生成地图")
        self.new_button.setText("录制新地图")
        self.new_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.recording_state_changed.emit(False)
        self.recording_finished.emit(map_name)
        self.worker = None

    def _on_failed(self, message):
        self.status_label.setText("录制失败")
        self.new_button.setText("录制新地图")
        self.new_button.setEnabled(True)
        self.continue_button.setEnabled(True)
        self.recording_state_changed.emit(False)
        self.worker = None
        QMessageBox.warning(self, "录制失败", message)

    def _update_preview(self, image):
        if image is None:
            return
        height, width, channels = image.shape
        from PySide6.QtGui import QImage

        qimage = QImage(
            image.data,
            width,
            height,
            width * channels,
            QImage.Format_BGR888,
        ).copy()
        self._preview_pixmap = QPixmap.fromImage(qimage)
        self._refresh_preview_pixmap()

    def _refresh_preview_pixmap(self):
        if self._preview_pixmap.isNull():
            return
        available = self.preview.contentsRect().size()
        available.setWidth(max(1, available.width() - 20))
        available.setHeight(max(1, available.height() - 20))
        self.preview.setPixmap(
            self._preview_pixmap.scaled(
                available,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_preview_pixmap()

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(3000)
