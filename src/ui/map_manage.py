"""Map manage hub + rope/bounds/route/monster sub-pages for MapManagementTab."""
from __future__ import annotations

import os
import time

import cv2
import numpy as np

from PySide6.QtCore import QPoint, QRect, QSize, QThread, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QDoubleValidator,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import logger
from src.utils.map_overlay import (
    bgr_to_qimage_bytes,
    clamp_range,
    load_map_bgr,
    ratio_to_x,
    x_to_ratio,
    render_bounds_overlay,
    render_map_base,
    render_ropes_overlay,
)
from src.utils.paths import MINIMAPS, minimap_dir
from src.utils.patrol import load_patrol, patrol_path, save_patrol
from src.utils.ropes import delete_edge, load_ropes, ropes_path


def _bgr_to_pixmap(image) -> QPixmap:
    arr = bgr_to_qimage_bytes(image)
    if arr is None:
        return QPixmap()
    height, width, channels = arr.shape
    qimage = QImage(
        arr.data,
        width,
        height,
        width * channels,
        QImage.Format_BGR888,
    ).copy()
    return QPixmap.fromImage(qimage)


def _fit_preview(label: QLabel, pixmap: QPixmap, max_height: int = 320) -> None:
    if pixmap.isNull():
        label.setPixmap(QPixmap())
        label.setText("暂无 map.png")
        return
    label.setText("")
    scaled = pixmap.scaled(
        label.width() if label.width() > 40 else 480,
        max_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    label.setPixmap(scaled)


class RopeRecorderWorker(QThread):
    frame_ready = Signal(object)
    status_changed = Signal(str)
    recording_finished = Signal(str)
    failed = Signal(str)
    edges_changed = Signal()

    def __init__(self, map_name, config_path="", parent=None):
        super().__init__(parent)
        self.map_name = map_name
        self.config_path = config_path
        self.recorder = None

    def run(self):
        try:
            from src.utils.rope_recorder import (
                RopeRecorder,
                cfg_name_from_path,
                load_recorder_cfg,
            )

            cfg_name = cfg_name_from_path(self.config_path, default="tommy")
            cfg = load_recorder_cfg(cfg_name)
            self.recorder = RopeRecorder(self.map_name, cfg)
            self.status_changed.emit(
                f"绳子录制中：{self.map_name} — F6 开始 / F7 保存 / F9 退出"
            )
            while not self.isInterruptionRequested() and not self.recorder.is_terminated:
                started_at = time.time()
                prev_status = self.recorder.last_status
                was_recording = self.recorder.is_recording
                self.recorder.run_once()
                if self.recorder.img_frame_debug is not None:
                    self.frame_ready.emit(self.recorder.img_frame_debug.copy())
                if self.recorder.last_status and self.recorder.last_status != prev_status:
                    self.status_changed.emit(self.recorder.last_status)
                    if was_recording and not self.recorder.is_recording:
                        self.edges_changed.emit()
                elapsed = time.time() - started_at
                remaining_ms = int(max(0, 1.0 / self.recorder.fps_limit - elapsed) * 1000)
                if remaining_ms:
                    self.msleep(remaining_ms)
            if self.recorder is not None:
                self.recorder.is_terminated = True
                self.recorder.cleanup()
            self.status_changed.emit("绳子录制结束")
            self.recording_finished.emit(self.map_name)
        except Exception as error:
            logger.exception(f"[RopeRecorderWorker] {error}")
            if self.recorder is not None:
                try:
                    self.recorder.cleanup()
                except Exception:
                    pass
            self.failed.emit(str(error))

    def trigger_start(self):
        if self.recorder is not None:
            self.recorder.start_record()

    def trigger_save(self):
        if self.recorder is not None:
            edge = self.recorder.stop_record()
            if edge is not None:
                self.edges_changed.emit()

    def stop_recording(self):
        if self.recorder is not None:
            self.recorder.request_stop()
        else:
            self.requestInterruption()


class BoundaryRecorderWorker(QThread):
    """Live minimap capture session for patrol.yaml range via F6/F7."""

    frame_ready = Signal(object)
    status_changed = Signal(str)
    range_changed = Signal(float, float)
    range_saved = Signal(float, float)
    recording_finished = Signal(str)
    failed = Signal(str)

    def __init__(self, map_name, config_path="", parent=None):
        super().__init__(parent)
        self.map_name = map_name
        self.config_path = config_path
        self.recorder = None

    def run(self):
        try:
            from src.utils.boundary_recorder import BoundaryRecorder
            from src.utils.rope_recorder import cfg_name_from_path, load_recorder_cfg

            cfg_name = cfg_name_from_path(self.config_path, default="tommy")
            cfg = load_recorder_cfg(cfg_name)
            self.recorder = BoundaryRecorder(self.map_name, cfg)
            self.status_changed.emit(
                f"边界采集中：{self.map_name} — 左缘 F6 / 右缘 F7 采样（不写盘） / F9 退出"
            )
            if self.recorder.left_ratio is not None and self.recorder.right_ratio is not None:
                self.range_changed.emit(self.recorder.left_ratio, self.recorder.right_ratio)
            while not self.isInterruptionRequested() and not self.recorder.is_terminated:
                started_at = time.time()
                prev_status = self.recorder.last_status
                prev_left = self.recorder.left_ratio
                prev_right = self.recorder.right_ratio
                prev_saved = self.recorder.last_saved_range
                self.recorder.run_once()
                if self.recorder.img_frame_debug is not None:
                    self.frame_ready.emit(self.recorder.img_frame_debug.copy())
                if self.recorder.last_status and self.recorder.last_status != prev_status:
                    self.status_changed.emit(self.recorder.last_status)
                if (
                    self.recorder.left_ratio is not None
                    and self.recorder.right_ratio is not None
                    and (
                        self.recorder.left_ratio != prev_left
                        or self.recorder.right_ratio != prev_right
                        or self.recorder.last_saved_range != prev_saved
                    )
                ):
                    self.range_changed.emit(
                        float(self.recorder.left_ratio),
                        float(self.recorder.right_ratio),
                    )
                    if self.recorder.last_saved_range != prev_saved and self.recorder.last_saved_range is not None:
                        self.range_saved.emit(
                            float(self.recorder.left_ratio),
                            float(self.recorder.right_ratio),
                        )
                elapsed = time.time() - started_at
                remaining_ms = int(max(0, 1.0 / self.recorder.fps_limit - elapsed) * 1000)
                if remaining_ms:
                    self.msleep(remaining_ms)
            if self.recorder is not None:
                self.recorder.is_terminated = True
                self.recorder.cleanup()
            self.status_changed.emit("边界采集结束")
            self.recording_finished.emit(self.map_name)
        except Exception as error:
            logger.exception(f"[BoundaryRecorderWorker] {error}")
            if self.recorder is not None:
                try:
                    self.recorder.cleanup()
                except Exception:
                    pass
            self.failed.emit(str(error))

    def trigger_left(self):
        if self.recorder is not None:
            ratio = self.recorder.capture_left()
            if ratio is not None:
                right = self.recorder.right_ratio if self.recorder.right_ratio is not None else ratio
                self.range_changed.emit(float(self.recorder.left_ratio), float(right))

    def trigger_right(self):
        if self.recorder is not None:
            rng = self.recorder.capture_right()
            if rng is not None:
                self.range_changed.emit(float(rng[0]), float(rng[1]))
                self.range_saved.emit(float(rng[0]), float(rng[1]))

    def stop_recording(self):
        if self.recorder is not None:
            self.recorder.request_stop()
        else:
            self.requestInterruption()


class MapManageHubPage(QWidget):
    """Hub listing manage entries for one map."""

    back_requested = Signal()
    open_ropes = Signal()
    open_bounds = Signal()
    open_monsters = Signal()
    open_routes = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        back = QPushButton("← 返回地图列表")
        back.clicked.connect(self.back_requested.emit)
        self.title = QLabel("地图管理")
        self.title.setStyleSheet("font-weight: 700; color: #334155;")
        header.addWidget(back)
        header.addWidget(self.title)
        header.addStretch(1)
        layout.addLayout(header)

        hint = QLabel("选择要编辑的项目：绳子、边界、怪物、路线。")
        hint.setStyleSheet("color: #718096;")
        layout.addWidget(hint)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: #475569;")
        layout.addWidget(self.summary)

        for text, signal in (
            ("绳子（查看 / 删除）", self.open_ropes),
            ("边界（巡逻范围 / preferred_y）", self.open_bounds),
            ("怪物", self.open_monsters),
            ("路线（route*.png）", self.open_routes),
        ):
            btn = QPushButton(text)
            btn.setMinimumHeight(44)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)
        layout.addStretch(1)

    def set_map(self, map_name: str, display_name: str, summary: str = ""):
        self.title.setText(f"管理 · {display_name}")
        self.summary.setText(summary or f"地图 id：{map_name}")


class RopeManagePage(QWidget):
    """Annotated minimap + in-place rope recording (no tab jump)."""

    back_requested = Signal()
    resources_changed = Signal()
    recording_state_changed = Signal(bool)

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
        self.map_name = ""
        self.worker = None
        self._live_mode = False
        self._preview_pixmap = QPixmap()
        self._syncing_canvas = False
        self._syncing_canvas = False

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        back = QPushButton("← 返回管理")
        back.clicked.connect(self._on_back)
        self.title = QLabel("绳子")
        self.title.setStyleSheet("font-weight: 700; color: #334155;")
        header.addWidget(back)
        header.addWidget(self.title)
        header.addStretch(1)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_edges)
        header.addWidget(refresh)
        layout.addLayout(header)

        self.path_label = QLabel("")
        self.path_label.setStyleSheet("color: #718096;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.hint = QLabel("小地图上绘制已录绳子。点「去录制」在本页现场录制（F6/F7），不跳转录制 Tab。")
        self.hint.setStyleSheet("color: #718096;")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.preview = QLabel("暂无 map.png")
        self.preview.setObjectName("ropeManagePreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(200)
        self.preview.setMaximumHeight(340)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.preview.setStyleSheet(
            "QLabel#ropeManagePreview {"
            " background: #0f172a; border-radius: 10px; color: #94a3b8; }"
        )
        layout.addWidget(self.preview)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #475569;")
        layout.addWidget(self.status_label)

        self.edge_list = QListWidget()
        self.edge_list.setObjectName("ropeManageEdgeList")
        self.edge_list.setMaximumHeight(140)
        self.edge_list.setStyleSheet(
            """
            QListWidget#ropeManageEdgeList::item {
                min-height: 32px;
                padding: 4px 10px;
                margin: 2px 0;
                border-radius: 7px;
            }
            QListWidget#ropeManageEdgeList::item:hover {
                background-color: #f0efff;
            }
            QListWidget#ropeManageEdgeList::item:selected {
                color: white;
                background-color: #6657d9;
            }
            """
        )
        self.edge_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.edge_list)

        actions = QHBoxLayout()
        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setObjectName("dangerOutlineButton")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.record_btn = QPushButton("去录制")
        self.record_btn.setObjectName("secondaryActionButton")
        self.record_btn.setMinimumHeight(40)
        self.record_btn.clicked.connect(self._toggle_record)
        self.btn_f6 = QPushButton("开始边 F6")
        self.btn_f6.clicked.connect(self._manual_start)
        self.btn_f6.setEnabled(False)
        self.btn_f7 = QPushButton("保存边 F7")
        self.btn_f7.clicked.connect(self._manual_save)
        self.btn_f7.setEnabled(False)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        actions.addWidget(self.btn_f6)
        actions.addWidget(self.btn_f7)
        actions.addWidget(self.record_btn)
        layout.addLayout(actions)

    def set_map(self, map_name: str):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(2000)
            self.worker = None
            self._set_record_idle()
        self.map_name = map_name
        display = self.repository.display_name(map_name)
        self.title.setText(f"绳子 · {display}")
        self.path_label.setText(f"文件：{ropes_path(map_name)}")
        self.refresh_edges()

    def refresh_edges(self):
        self.edge_list.clear()
        if not self.map_name:
            return
        doc = load_ropes(self.map_name)
        edges = doc.get("edges") or []
        if not edges:
            item = QListWidgetItem("（尚无绳子 — 请点「去录制」）")
            item.setFlags(Qt.NoItemFlags)
            item.setSizeHint(QSize(0, 36))
            self.edge_list.addItem(item)
        else:
            for i, edge in enumerate(edges, start=1):
                direction = str(edge.get("direction") or "").lower()
                dir_cn = "上" if direction == "up" else ("下" if direction == "down" else direction)
                label = f"绳子{i}"
                if dir_cn:
                    label = f"{label}（{dir_cn}）"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, edge.get("id"))
                item.setSizeHint(QSize(0, 36))
                self.edge_list.addItem(item)
        if not self._live_mode:
            self._show_annotated_preview()

    def _selected_edge_id(self):
        item = self.edge_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _on_selection_changed(self, _current, _previous):
        if not self._live_mode:
            self._show_annotated_preview()

    def _show_annotated_preview(self):
        if not self.map_name:
            return
        doc = load_ropes(self.map_name)
        edges = doc.get("edges") or []
        base = load_map_bgr(self.map_name)
        preview = render_ropes_overlay(
            base,
            edges,
            scale=4,
            selected_id=self._selected_edge_id(),
        )
        self._preview_pixmap = _bgr_to_pixmap(preview)
        _fit_preview(self.preview, self._preview_pixmap)
        self.status_label.setText(
            f"已录 {len(edges)} 条绳子（地图描点预览）"
            if edges
            else "尚无绳子描点 — 点「去录制」开始"
        )

    def _show_live_frame(self, frame):
        if frame is None:
            return
        self._live_mode = True
        left, right = self._current_range()
        # Live recorder frame already has HUD; show as base without extra lines.
        self.preview.set_map_image(frame, left, right, preferred_y=None)

    def _set_record_idle(self):
        self._live_mode = False
        self.record_btn.setText("去录制")
        self.btn_f6.setEnabled(False)
        self.btn_f7.setEnabled(False)
        self.delete_btn.setEnabled(True)

    def _toggle_record(self):
        if self.worker is not None and self.worker.isRunning():
            self.status_label.setText("正在停止录制…")
            self.worker.stop_recording()
            return
        if not self.map_name:
            QMessageBox.warning(self, "去录制", "未选择地图。")
            return
        if self.bot_running_provider and self.bot_running_provider():
            tip = (
                "检测到挂机正在运行。录制绳子需要独占键鼠/画面，"
                "是否先停止挂机再开始录制？"
            )
            if QMessageBox.question(self, "去录制", tip) != QMessageBox.Yes:
                return
            if self.stop_bot_callback:
                self.stop_bot_callback()
        tip = (
            f"将在本页为 “{self.repository.display_name(self.map_name)}” 录制绳子。\n\n"
            "1. 不要同时开智能巡逻挂机\n"
            "2. 走到绳子起点按 F6（或点「开始边」）\n"
            "3. 爬到另一层按 F7 保存（写入 ropes.yaml）\n"
            "4. 可继续录多条；F9 或再次点按钮结束并回到地图描点"
        )
        if QMessageBox.question(self, "去录制", tip) != QMessageBox.Yes:
            return
        config_path = self.config_path_provider() if self.config_path_provider else ""
        self.worker = RopeRecorderWorker(
            self.map_name, config_path=config_path, parent=self
        )
        self.worker.status_changed.connect(self.status_label.setText)
        self.worker.frame_ready.connect(self._show_live_frame)
        self.worker.edges_changed.connect(self._on_edge_saved)
        self.worker.recording_finished.connect(self._on_record_finished)
        self.worker.failed.connect(self._on_record_failed)
        self.record_btn.setText("停止录制")
        self.btn_f6.setEnabled(True)
        self.btn_f7.setEnabled(True)
        self.delete_btn.setEnabled(False)
        self._live_mode = True
        self.recording_state_changed.emit(True)
        self.worker.start()

    def _manual_start(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.trigger_start()

    def _manual_save(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.trigger_save()

    def _on_edge_saved(self):
        # F7 save complete: end session and restore annotated preview.
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
        self.edge_list.blockSignals(True)
        selected = self._selected_edge_id()
        doc = load_ropes(self.map_name)
        edges = doc.get("edges") or []
        self.edge_list.clear()
        for i, edge in enumerate(edges, start=1):
            direction = str(edge.get("direction") or "").lower()
            dir_cn = "上" if direction == "up" else ("下" if direction == "down" else direction)
            label = f"绳子{i}"
            if dir_cn:
                label = f"{label}（{dir_cn}）"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, edge.get("id"))
            item.setSizeHint(QSize(0, 36))
            self.edge_list.addItem(item)
            if selected and edge.get("id") == selected:
                self.edge_list.setCurrentItem(item)
        self.edge_list.blockSignals(False)
        self.resources_changed.emit()

    def _on_record_finished(self, map_name: str):
        self.worker = None
        self._set_record_idle()
        self.recording_state_changed.emit(False)
        self.refresh_edges()
        self.status_label.setText(f"绳子录制结束：{map_name}（已恢复地图描点）")

    def _on_record_failed(self, message: str):
        self.worker = None
        self._set_record_idle()
        self.recording_state_changed.emit(False)
        self.refresh_edges()
        QMessageBox.warning(self, "绳子录制失败", message)

    def _delete_selected(self):
        item = self.edge_list.currentItem()
        if item is None or not item.data(Qt.UserRole):
            return
        edge_id = item.data(Qt.UserRole)
        if (
            QMessageBox.question(self, "删除绳子", f"确定删除 {item.text()} 吗？")
            != QMessageBox.Yes
        ):
            return
        delete_edge(self.map_name, edge_id)
        self.refresh_edges()
        self.resources_changed.emit()

    def _on_back(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(2000)
            self.worker = None
            self._set_record_idle()
            self.recording_state_changed.emit(False)
        self.back_requested.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # BoundsPreviewCanvas handles its own resize/paint.

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(3000)
            self.worker = None
            self.recording_state_changed.emit(False)



class BoundsPreviewCanvas(QWidget):
    """Larger minimap preview with draggable L/R bound lines (memory only)."""

    range_changed = Signal(float, float)

    _MIN_GAP = 0.02
    _GRAB_PX = 12
    # Native map pixels only — do NOT pre-upsample; fit/zoom handle display size.
    _BASE_SCALE = 1
    _ZOOM_MIN = 0.15
    _ZOOM_MAX = 8.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("boundsPreviewCanvas")
        self.setMinimumSize(520, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet(
            "QWidget#boundsPreviewCanvas {"
            " background: #0f172a; border-radius: 10px; }"
        )
        self._map_bgr = None
        self._base_pixmap = QPixmap()
        self._left = 0.25
        self._right = 0.75
        self._preferred_y = None
        self._zoom = 1.0
        self._pan = QPoint(0, 0)
        self._user_zoomed = False
        self._drag = None  # "left" | "right" | "pan" | None
        self._hover = None
        self._press_pos = QPoint()
        self._pan_at_press = QPoint()

    def set_map_image(self, map_bgr, left: float, right: float, preferred_y=None):
        self._map_bgr = None if map_bgr is None else map_bgr.copy()
        self._preferred_y = preferred_y
        self._left, self._right = clamp_range(left, right, self._MIN_GAP)
        self._rebuild_base()
        self._user_zoomed = False
        self.fit_to_view()
        self.update()

    def set_range(self, left: float, right: float, *, emit: bool = False):
        left, right = clamp_range(left, right, self._MIN_GAP)
        if abs(left - self._left) < 1e-9 and abs(right - self._right) < 1e-9:
            return
        self._left, self._right = left, right
        self.update()
        if emit:
            self.range_changed.emit(self._left, self._right)

    def current_range(self):
        return self._left, self._right

    def _rebuild_base(self):
        if self._map_bgr is None:
            self._base_pixmap = QPixmap()
            return
        canvas = render_map_base(
            self._map_bgr,
            scale=self._BASE_SCALE,
            preferred_y=self._preferred_y,
        )
        self._base_pixmap = _bgr_to_pixmap(canvas)

    def fit_to_view(self):
        """Contain entire map in the widget (letterbox), centered."""
        if self._base_pixmap.isNull():
            self._zoom = 1.0
            self._pan = QPoint(0, 0)
            return
        bw = max(1, self._base_pixmap.width())
        bh = max(1, self._base_pixmap.height())
        ww = max(1, self.width() - 16)
        wh = max(1, self.height() - 28)
        self._zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, min(ww / bw, wh / bh)))
        self._pan = QPoint(0, 0)
        self._user_zoomed = False

    def _map_rect(self) -> QRect:
        if self._base_pixmap.isNull():
            return QRect()
        pw = max(1, int(round(self._base_pixmap.width() * self._zoom)))
        ph = max(1, int(round(self._base_pixmap.height() * self._zoom)))
        x = (self.width() - pw) // 2 + self._pan.x()
        y = (self.height() - ph) // 2 + self._pan.y()
        return QRect(x, y, pw, ph)

    def _native_w(self) -> int:
        if self._map_bgr is None:
            return max(1, self._base_pixmap.width())
        try:
            return max(1, int(self._map_bgr.shape[1]))
        except Exception:
            return max(1, self._base_pixmap.width())

    def _ratio_from_pos(self, pos: QPoint) -> float:
        """Map mouse x → ratio using native minimap width (same as smart_patrol)."""
        rect = self._map_rect()
        if rect.width() <= 0:
            return 0.5
        # display_x / display_w == native_x / native_w when full map fills rect
        local_x = float(pos.x() - rect.left())
        native_x = local_x * float(self._native_w()) / float(rect.width())
        return x_to_ratio(native_x, self._native_w())

    def _x_for_ratio(self, ratio: float) -> int:
        rect = self._map_rect()
        if rect.width() <= 0:
            return rect.left()
        # Project native pixel onto display rect (keeps L/R aligned with runtime /w)
        nx = ratio_to_x(ratio, self._native_w())
        nw = float(self._native_w())
        dx = int(round(nx * float(rect.width()) / nw))
        return rect.left() + min(rect.width() - 1, max(0, dx))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0f172a"))
        rect = self._map_rect()
        if self._base_pixmap.isNull() or not rect.isValid() or rect.width() < 2:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无 map.png")
            painter.end()
            return
        scaled = self._base_pixmap.scaled(
            rect.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )
        painter.drawPixmap(rect.topLeft(), scaled)

        x0 = self._x_for_ratio(self._left)
        x1 = self._x_for_ratio(self._right)
        painter.fillRect(
            QRect(x0, rect.top(), max(1, x1 - x0), rect.height()),
            QColor(60, 140, 80, 75),
        )

        def _draw_bound(x, label, active):
            color = QColor("#fbbf24") if active else QColor("#5ac8ff")
            painter.fillRect(
                QRect(x - self._GRAB_PX, rect.top(), self._GRAB_PX * 2, rect.height()),
                QColor(color.red(), color.green(), color.blue(), 45),
            )
            painter.setPen(QPen(color, 3 if active else 2))
            painter.drawLine(x, rect.top(), x, rect.bottom())
            painter.drawText(x + 4, rect.top() + 18, label)

        _draw_bound(x0, "L", self._drag == "left" or self._hover == "left")
        _draw_bound(x1, "R", self._drag == "right" or self._hover == "right")
        painter.setPen(QColor("#7dd3fc"))
        painter.drawText(
            12,
            self.height() - 12,
            f"range [{self._left:.3f}, {self._right:.3f}]  "
            f"zoom {self._zoom:.2f}×  滚轮缩放 · 空白平移 · 拖 L/R · 保存边界",
        )
        painter.end()

    def _hit_test(self, pos: QPoint):
        if not self._map_rect().isValid():
            return None
        x0 = self._x_for_ratio(self._left)
        x1 = self._x_for_ratio(self._right)
        dl, dr = abs(pos.x() - x0), abs(pos.x() - x1)
        # Prefer the closer line when both in grab range
        if dl <= self._GRAB_PX and dl <= dr:
            return "left"
        if dr <= self._GRAB_PX:
            return "right"
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        self._press_pos = pos
        hit = self._hit_test(pos)
        if hit:
            self._drag = hit
            self.setCursor(Qt.SizeHorCursor)
        else:
            self._drag = "pan"
            self._pan_at_press = QPoint(self._pan)
            self.setCursor(Qt.ClosedHandCursor)
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self._drag == "left":
            left = self._ratio_from_pos(pos)
            left = min(left, self._right - self._MIN_GAP)
            left = max(0.0, left)
            self._left = left
            self.range_changed.emit(self._left, self._right)
            self.update()
            return
        if self._drag == "right":
            right = self._ratio_from_pos(pos)
            right = max(right, self._left + self._MIN_GAP)
            right = min(1.0, right)
            self._right = right
            self.range_changed.emit(self._left, self._right)
            self.update()
            return
        if self._drag == "pan":
            self._pan = self._pan_at_press + (pos - self._press_pos)
            self.update()
            return
        self._hover = self._hit_test(pos)
        self.setCursor(Qt.SizeHorCursor if self._hover else Qt.OpenHandCursor)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None
        self._hover = self._hit_test(
            event.position().toPoint() if hasattr(event, "position") else event.pos()
        )
        self.setCursor(Qt.SizeHorCursor if self._hover else Qt.OpenHandCursor)
        self.update()
        return super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.12 if delta > 0 else (1.0 / 1.12)
        old_zoom = self._zoom
        new_zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-9:
            return
        # Zoom toward cursor so the map under the pointer stays put
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        rect = self._map_rect()
        if rect.isValid() and rect.width() > 0 and rect.height() > 0:
            fx = (pos.x() - rect.left()) / float(rect.width())
            fy = (pos.y() - rect.top()) / float(rect.height())
            self._zoom = new_zoom
            new_rect = self._map_rect()
            # Keep the same map fraction under the cursor
            target_x = pos.x() - int(round(fx * new_rect.width()))
            target_y = pos.y() - int(round(fy * new_rect.height()))
            # _map_rect centers with pan; invert to update pan
            centered_x = (self.width() - new_rect.width()) // 2
            centered_y = (self.height() - new_rect.height()) // 2
            self._pan = QPoint(target_x - centered_x, target_y - centered_y)
        else:
            self._zoom = new_zoom
        self._user_zoomed = True
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._user_zoomed:
            self.fit_to_view()
        self.update()

    def mouseDoubleClickEvent(self, event):
        # Double-click blank area → reset to full map
        if event.button() == Qt.LeftButton:
            self.fit_to_view()
            self.update()
            return
        return super().mouseDoubleClickEvent(event)


class BoundsManagePage(QWidget):
    """Annotated minimap bounds + in-place F6/F7 capture session."""

    back_requested = Signal()
    resources_changed = Signal()
    recording_state_changed = Signal(bool)

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
        self.map_name = ""
        self.worker = None
        self._live_mode = False
        self._preview_pixmap = QPixmap()

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        back = QPushButton("← 返回管理")
        back.clicked.connect(self._on_back)
        self.title = QLabel("边界")
        self.title.setStyleSheet("font-weight: 700; color: #334155;")
        header.addWidget(back)
        header.addWidget(self.title)
        header.addStretch(1)
        layout.addLayout(header)

        note = QLabel(
            "预览默认展示全图（双击恢复）。滚轮缩放、拖空白平移、拖 L/R 调边界；F6/F7 只采样；点「保存边界」写盘。"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #718096;")
        layout.addWidget(note)

        self.path_label = QLabel("")
        self.path_label.setStyleSheet("color: #475569;")
        layout.addWidget(self.path_label)

        self.preview = BoundsPreviewCanvas()
        self.preview.setMinimumHeight(320)
        self.preview.range_changed.connect(self._on_canvas_range_changed)
        layout.addWidget(self.preview, stretch=1)

        self.capture_status = QLabel("未开始采集")
        self.capture_status.setWordWrap(True)
        self.capture_status.setStyleSheet("color: #475569;")
        layout.addWidget(self.capture_status)

        capture_box = QGroupBox("现场采集 range")
        capture_layout = QVBoxLayout(capture_box)
        cap_btns = QHBoxLayout()
        self.capture_toggle = QPushButton("开始采集会话 F6/F7")
        self.capture_toggle.setObjectName("secondaryActionButton")
        self.capture_toggle.setMinimumHeight(40)
        self.capture_toggle.clicked.connect(self._toggle_capture)
        self.btn_cap_left = QPushButton("捕获左 F6")
        self.btn_cap_left.clicked.connect(self._manual_left)
        self.btn_cap_left.setEnabled(False)
        self.btn_cap_right = QPushButton("采样右 F7")
        self.btn_cap_right.clicked.connect(self._manual_right)
        self.btn_cap_right.setEnabled(False)
        cap_btns.addWidget(self.capture_toggle)
        cap_btns.addWidget(self.btn_cap_left)
        cap_btns.addWidget(self.btn_cap_right)
        capture_layout.addLayout(cap_btns)
        layout.addWidget(capture_box)

        self.advanced_box = QGroupBox("高级数值（可选）")
        self.advanced_box.setCheckable(True)
        self.advanced_box.setChecked(False)
        adv_layout = QVBoxLayout(self.advanced_box)
        self.advanced_content = QWidget()
        form = QFormLayout(self.advanced_content)
        self.range_left = QLineEdit()
        self.range_right = QLineEdit()
        for edit in (self.range_left, self.range_right):
            edit.setValidator(QDoubleValidator(0.0, 1.0, 3))
            edit.textChanged.connect(self._on_range_edit_changed)
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("左"))
        range_row.addWidget(self.range_left)
        range_row.addWidget(QLabel("右"))
        range_row.addWidget(self.range_right)
        range_wrap = QWidget()
        range_wrap.setLayout(range_row)
        form.addRow("巡逻 range [0–1]:", range_wrap)

        self.preferred_y = QLineEdit()
        self.preferred_y.setPlaceholderText("留空 = 不覆盖 / 用绳子 end")
        self.preferred_y.setValidator(QDoubleValidator(-9999.0, 9999.0, 2))
        form.addRow("preferred_y:", self.preferred_y)

        self.preferred_y_tol = QLineEdit()
        self.preferred_y_tol.setValidator(QDoubleValidator(0.0, 9999.0, 2))
        form.addRow("preferred_y_tol:", self.preferred_y_tol)

        self.rope_enable = QCheckBox("启用绳子 Return（rope_enable）")
        form.addRow("", self.rope_enable)
        adv_layout.addWidget(self.advanced_content)
        self.advanced_box.toggled.connect(self._on_advanced_toggled)
        layout.addWidget(self.advanced_box)
        self._on_advanced_toggled(False)

        save_btn = QPushButton("保存边界")
        save_btn.setObjectName("secondaryActionButton")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)
        layout.addStretch(1)

    def _on_advanced_toggled(self, checked: bool):
        if hasattr(self, "advanced_content") and self.advanced_content is not None:
            self.advanced_content.setVisible(bool(checked))

    def set_map(self, map_name: str):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(2000)
            self.worker = None
            self._set_capture_idle()
        self.map_name = map_name
        display = self.repository.display_name(map_name)
        self.title.setText(f"边界 · {display}")
        self.path_label.setText(f"文件：{patrol_path(map_name)}")
        doc = load_patrol(map_name)
        left, right = doc.get("range") or [0.15, 0.85]
        self.range_left.setText(f"{float(left):.3f}")
        self.range_right.setText(f"{float(right):.3f}")
        py = doc.get("preferred_y")
        self.preferred_y.setText("" if py is None else str(py))
        self.preferred_y_tol.setText(str(doc.get("preferred_y_tol", 12)))
        self.rope_enable.setChecked(bool(doc.get("rope_enable", True)))
        self._show_annotated_preview()

    def _current_range(self):
        try:
            left = float(self.range_left.text().strip() or "0.25")
            right = float(self.range_right.text().strip() or "0.75")
        except ValueError:
            left, right = 0.25, 0.75
        if left > right:
            left, right = right, left
        return left, right

    def _show_annotated_preview(self):
        if not self.map_name:
            return
        left, right = self._current_range()
        py_text = self.preferred_y.text().strip()
        preferred_y = None
        if py_text:
            try:
                preferred_y = float(py_text)
            except ValueError:
                preferred_y = None
        base = load_map_bgr(self.map_name)
        self._preview_pixmap = QPixmap()  # unused; canvas holds image
        if not self._live_mode:
            self.preview.set_map_image(base, left, right, preferred_y=preferred_y)
            self.capture_status.setText(
                f"巡逻范围预览  left={left:.3f}  right={right:.3f}（拖拽线条后需点保存）"
            )

    def _show_live_frame(self, frame):
        if frame is None:
            return
        self._live_mode = True
        pix = _bgr_to_pixmap(frame)
        _fit_preview(self.preview, pix, max_height=340)

    def _on_back(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(2000)
            self.worker = None
            self._set_capture_idle()
            self.recording_state_changed.emit(False)
        self.back_requested.emit()

    def _set_capture_idle(self):
        self._live_mode = False
        self.capture_toggle.setText("开始采集会话 F6/F7")
        self.btn_cap_left.setEnabled(False)
        self.btn_cap_right.setEnabled(False)

    def _toggle_capture(self):
        if self.worker is not None and self.worker.isRunning():
            self.capture_status.setText("正在停止采集…")
            self.worker.stop_recording()
            return
        if not self.map_name:
            QMessageBox.warning(self, "边界采集", "未选择地图。")
            return
        if self.bot_running_provider and self.bot_running_provider():
            tip = (
                "检测到挂机正在运行。采集边界需要独占键鼠/画面，"
                "是否先停止挂机再开始采集？"
            )
            if QMessageBox.question(self, "边界采集", tip) != QMessageBox.Yes:
                return
            if self.stop_bot_callback:
                self.stop_bot_callback()
        tip = (
            f"将为地图 “{self.repository.display_name(self.map_name)}” 采集巡逻 range。\n\n"
            "1. 不要同时开智能巡逻挂机\n"
            "2. 走到平台左侧安全边缘按 F6（或点「捕获左」）\n"
            "3. 走到右侧安全边缘按 F7（仅采样，不写盘；左>右预览时自动对调）\n"
            "4. F9 结束会话；最后点「保存边界」写入磁盘"
        )
        if QMessageBox.question(self, "边界采集", tip) != QMessageBox.Yes:
            return
        config_path = self.config_path_provider() if self.config_path_provider else ""
        self.worker = BoundaryRecorderWorker(
            self.map_name, config_path=config_path, parent=self
        )
        self.worker.status_changed.connect(self.capture_status.setText)
        self.worker.frame_ready.connect(self._show_live_frame)
        self.worker.range_changed.connect(self._on_range_captured)
        self.worker.range_saved.connect(self._on_range_saved)
        self.worker.recording_finished.connect(self._on_capture_finished)
        self.worker.failed.connect(self._on_capture_failed)
        self.capture_toggle.setText("停止采集会话")
        self.btn_cap_left.setEnabled(True)
        self.btn_cap_right.setEnabled(True)
        self._live_mode = True
        self.recording_state_changed.emit(True)
        self.worker.start()

    def _manual_left(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.trigger_left()

    def _manual_right(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.trigger_right()

    def _on_range_captured(self, left: float, right: float):
        self._syncing_canvas = True
        try:
            self.range_left.setText(f"{float(left):.3f}")
            self.range_right.setText(f"{float(right):.3f}")
        finally:
            self._syncing_canvas = False
        if not self._live_mode:
            self.preview.set_range(float(left), float(right), emit=False)
        else:
            self.preview.set_range(float(left), float(right), emit=False)

    def _on_range_saved(self, left: float, right: float):
        # F7 is sample-only now (recorder no longer writes disk).
        self._on_range_captured(left, right)
        self.capture_status.setText(
            f"已采样（未保存） left={float(left):.3f}  right={float(right):.3f} — 请点「保存边界」"
        )

    def _on_capture_finished(self, map_name: str):
        self.worker = None
        self._set_capture_idle()
        self.recording_state_changed.emit(False)
        if self.map_name:
            doc = load_patrol(self.map_name)
            left, right = doc.get("range") or [0.15, 0.85]
            self.range_left.setText(f"{float(left):.3f}")
            self.range_right.setText(f"{float(right):.3f}")
        self._show_annotated_preview()
        self.capture_status.setText(f"边界采集结束：{map_name}（已恢复地图描点）")

    def _on_capture_failed(self, message: str):
        self.worker = None
        self._set_capture_idle()
        self.recording_state_changed.emit(False)
        self._show_annotated_preview()
        QMessageBox.warning(self, "边界采集失败", message)


    def _on_range_edit_changed(self, _text=""):
        if getattr(self, "_syncing_canvas", False) or self._live_mode:
            return
        if not self.map_name:
            return
        left, right = self._current_range()
        self.preview.set_range(left, right, emit=False)

    def _on_canvas_range_changed(self, left: float, right: float):
        self._syncing_canvas = True
        try:
            self.range_left.setText(f"{float(left):.3f}")
            self.range_right.setText(f"{float(right):.3f}")
        finally:
            self._syncing_canvas = False
        self.capture_status.setText(
            f"已拖拽（未保存） left={left:.3f}  right={right:.3f}"
        )

    def _save(self):
        if not self.map_name:
            return
        try:
            left = float(self.range_left.text().strip())
            right = float(self.range_right.text().strip())
            tol = float(self.preferred_y_tol.text().strip() or "12")
        except ValueError:
            QMessageBox.warning(self, "保存边界", "请输入有效数字。")
            return
        if left > right:
            left, right = right, left
            self.range_left.setText(f"{left:.3f}")
            self.range_right.setText(f"{right:.3f}")
        py_text = self.preferred_y.text().strip()
        preferred_y = None
        if py_text:
            try:
                preferred_y = float(py_text)
            except ValueError:
                QMessageBox.warning(self, "保存边界", "preferred_y 无效。")
                return
        doc = {
            "map": self.map_name,
            "range": [left, right],
            "preferred_y": preferred_y,
            "preferred_y_tol": tol,
            "rope_enable": self.rope_enable.isChecked(),
        }
        path = save_patrol(self.map_name, doc)
        try:
            from src.utils.ropes import load_ropes, save_ropes

            ropes = load_ropes(self.map_name)
            ropes["preferred_y"] = preferred_y
            ropes["preferred_y_tol"] = tol
            save_ropes(self.map_name, ropes)
        except Exception as err:
            logger.warning(f"[BoundsManagePage] sync ropes.yaml failed: {err}")
        self._show_annotated_preview()
        QMessageBox.information(self, "保存边界", f"已保存到\n{path}")
        self.resources_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._live_mode and not self._preview_pixmap.isNull():
            _fit_preview(self.preview, self._preview_pixmap)

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop_recording()
            self.worker.wait(3000)
            self.worker = None
            self.recording_state_changed.emit(False)
