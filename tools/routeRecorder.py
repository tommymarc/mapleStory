'''
Auto generate route map 
'''
# Standard import
import time
import argparse
import sys
import os
from src.utils.paths import MINIMAPS
import shutil
import glob
import re

# CV import
import numpy as np
import cv2

# local import
from src.utils.global_var import WINDOW_WORKING_SIZE
from src.utils.logger import logger
from src.utils.common import (
    draw_rectangle,
    get_minimap_loc_size, get_player_location_on_minimap,
    to_opencv_hsv, load_yaml, override_cfg, is_mac, load_image,
    match_minimap_on_map, is_img_16_to_9,
)
from src.input.KeyBoardListener import KeyBoardListener
if is_mac():
    from src.input.GameWindowCapturorForMac import GameWindowCapturor
else:
    from src.input.GameWindowCapturor import GameWindowCapturor

class RouteRecorder():
    '''
    Route recorder
    '''
    def update_info_on_img_frame_debug(self):
        '''
        update_info_on_img_frame_debug
        '''
        # Print text at bottom left corner
        self.fps = round(1.0 / (time.time() - self.t_last_frame))
        text_y_interval = 23
        text_y_start = 550
        dt_save_route = time.time() - self.kb.t_func_key[1]
        dt_clear_route = time.time() - self.kb.t_func_key[2]
        dt_stop = time.time() - self.kb.t_func_key[3]
        text_list = [
            f"FPS: {self.fps}",
            f"Press 'F1' to {'pause' if self.is_enable else 'start'} route record",
            f"Press 'F2' to save route{' : Saved' if dt_save_route < 0.7 else ''}",
            f"Press 'F3' to clear current route{' : Cleared' if dt_clear_route < 0.7 else ''}",
            f"Press 'F4' to stop recording{' : Stopping' if dt_stop < 0.7 else ''}",
        ]
        for idx, text in enumerate(text_list):
            cv2.putText(
                self.img_frame_debug, text,
                (10, text_y_start + text_y_interval*idx),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255),
                2, cv2.LINE_AA
            )

        # Draw minimap rectangle on img debug
        draw_rectangle(
            self.img_frame_debug,
            self.loc_minimap,
            self.img_minimap.shape[:2],
            (0, 0, 255), "minimap",thickness=1
        )

        # Compute crop region with boundary check
        crop_w, crop_h = 80, 80
        x0 = max(0, self.loc_player_global[0] - crop_w // 2)
        y0 = max(0, self.loc_player_global[1] - crop_h // 2)
        x1 = min(self.img_route_debug.shape[1], x0 + crop_w)
        y1 = min(self.img_route_debug.shape[0], y0 + crop_h)

        # Crop region
        mini_map_crop = self.img_route_debug[y0:y1, x0:x1]
        mini_map_crop = cv2.resize(mini_map_crop,
                                (int(mini_map_crop.shape[1] * 3),
                                 int(mini_map_crop.shape[0] * 3)),
                                interpolation=cv2.INTER_NEAREST)
        # Paste into top-right corner of self.img_frame_debug
        h_crop, w_crop = mini_map_crop.shape[:2]
        h_frame, w_frame = self.img_frame_debug.shape[:2]
        x_paste = w_frame - w_crop - 10  # 10px margin from right
        y_paste = 70
        self.img_frame_debug[y_paste:y_paste + h_crop, x_paste:x_paste + w_crop] = mini_map_crop

        # Draw border around minimap
        cv2.rectangle(
            self.img_frame_debug,
            (x_paste, y_paste),
            (x_paste + w_crop, y_paste + h_crop),
            color=(255, 255, 255),   # White border
            thickness=2
        )

    def update_img_frame_debug(self):
        '''
        update_img_frame_debug
        '''
        if self.show_windows:
            cv2.imshow("Game Window Debug",
                       self.img_frame_debug[:self.cfg["ui_coords"]["ui_y_start"], :])
        # Update FPS timer
        self.t_last_frame = time.time()

    def get_player_location_on_global_map(self):
        '''
        get_player_location_on_global_map
        '''
        last_result = None if self.is_first_frame else self.loc_minimap_global
        self.loc_minimap_global, score, _ = match_minimap_on_map(
            self.img_map,
            self.img_minimap,
            last_result=last_result,
            mask=self.get_minimap_match_mask(),
        )
        loc_player_global = (
            self.loc_minimap_global[0] + self.loc_player_minimap[0],
            self.loc_minimap_global[1] + self.loc_player_minimap[1]
        )

        # Draw local minimap rectangle
        camera_bottom_right = (
            self.loc_minimap_global[0] + self.img_minimap.shape[1],
            self.loc_minimap_global[1] + self.img_minimap.shape[0]
        )
        cv2.rectangle(self.img_route_debug, self.loc_minimap_global,
                      camera_bottom_right, (0, 255, 255), 1)
        cv2.putText(
            self.img_route_debug,
            f"Minimap,score({round(score, 2)})",
            (self.loc_minimap_global[0], self.loc_minimap_global[1]+15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            (0, 255, 255), 1
        )

        # Draw player center
        cv2.circle(self.img_route_debug,
                   loc_player_global, radius=2,
                   color=(0, 255, 255), thickness=-1)

        return loc_player_global

    def get_minimap_match_mask(self):
        """Match only static minimap artwork, excluding live player markers."""
        mask = np.any(self.img_minimap > [2, 2, 2], axis=2).astype(np.uint8) * 255
        dynamic = np.zeros(self.img_minimap.shape[:2], dtype=np.uint8)
        player_color = np.asarray(
            self.cfg["minimap"].get("player_color", [0, 255, 255]),
            dtype=np.uint8,
        )
        dynamic = cv2.bitwise_or(
            dynamic,
            cv2.inRange(self.img_minimap, player_color, player_color),
        )
        other_color = np.asarray(
            self.cfg["minimap"].get("other_player_color", [0, 0, 255]),
            dtype=np.int16,
        )
        dynamic = cv2.bitwise_or(
            dynamic,
            cv2.inRange(
                self.img_minimap,
                np.clip(other_color - 20, 0, 255).astype(np.uint8),
                np.clip(other_color + 20, 0, 255).astype(np.uint8),
            ),
        )
        dynamic = cv2.dilate(dynamic, np.ones((7, 7), dtype=np.uint8))
        mask[dynamic > 0] = 0
        return mask

    def replace_color_on_map(self, lower_hsv, upper_hsv, replace_color=(0, 0, 0)):
        '''
        Replace pixels in self.img_map that fall within the given HSV range
        and are part of a connected component with area > 15.
        '''
        hsv_map = cv2.cvtColor(self.img_map, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_map, to_opencv_hsv(lower_hsv), to_opencv_hsv(upper_hsv))

        # Connected components
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

        for i in range(1, num_labels):  # skip background
            area = stats[i, cv2.CC_STAT_AREA]
            if area > 10:
                component_mask = (labels == i)
                self.img_map[component_mask] = replace_color

    def get_img_frame(self):
        '''
        get_img_frame
        '''
        # Get window game raw frame
        self.frame = self.capture.get_frame()
        if self.frame is None:
            self.last_status = "正在等待游戏窗口画面…"
            return

        # Windows Capture and MSS already return the game client. The recorder
        # previously removed title_bar_height a second time, cutting through
        # the top-left minimap and leaving continuation sessions on first frame
        # forever. Legacy/macOS capture paths still use the old title crop.
        if getattr(self.capture, "returns_client_frame", False):
            frame_no_title = self.frame
            if not is_img_16_to_9(frame_no_title, self.cfg):
                self.last_status = (
                    f"游戏画面比例异常：{frame_no_title.shape[1]}×"
                    f"{frame_no_title.shape[0]}"
                )
                return
            if not self._window_size_adapted:
                logger.info(
                    "[RouteRecorder] Using client capture "
                    f"{frame_no_title.shape[1]}x{frame_no_title.shape[0]}"
                )
                self._window_size_adapted = True
            return cv2.resize(
                frame_no_title,
                WINDOW_WORKING_SIZE,
                interpolation=cv2.INTER_NEAREST,
            )

        title_bar_height = int(self.cfg["game_window"]["title_bar_height"])
        if self.frame.shape[0] <= title_bar_height:
            self.last_status = "游戏窗口画面高度异常，请恢复窗口后重试"
            return
        frame_no_title = self.frame[title_bar_height:, :]
        normalized = self._normalize_window_frame(frame_no_title)
        if normalized is None:
            return

        return cv2.resize(
            normalized,
            WINDOW_WORKING_SIZE,
            interpolation=cv2.INTER_NEAREST,
        )

    def _normalize_window_frame(self, frame):
        """Crop small window borders or resize a ratio-compatible game frame."""
        expected_h, expected_w = map(int, self.cfg["game_window"]["size"])
        actual_h, actual_w = frame.shape[:2]
        if (actual_h, actual_w) == (expected_h, expected_w):
            return frame

        expected_ratio = expected_w / max(1, expected_h)
        actual_ratio = actual_w / max(1, actual_h)
        ratio_tolerance = float(
            self.cfg["game_window"].get("ratio_tolerance", 0.08)
        )
        scale_h = actual_h / max(1, expected_h)
        scale_w = actual_w / max(1, expected_w)
        close_scale = 0.80 <= scale_h <= 1.20 and 0.80 <= scale_w <= 1.20

        if abs(actual_ratio - expected_ratio) > ratio_tolerance or not close_scale:
            message = (
                f"窗口尺寸不匹配：当前 {actual_w}×{actual_h}，"
                f"期望约 {expected_w}×{expected_h}"
            )
            self.last_status = message
            now = time.monotonic()
            if now - self._last_window_size_warning >= 2.0:
                logger.error(message)
                self._last_window_size_warning = now
            return None

        if actual_h >= expected_h and actual_w >= expected_w:
            # After removing the title bar, any remaining vertical decoration
            # is at the bottom; horizontal decoration is symmetric.
            left = max(0, (actual_w - expected_w) // 2)
            normalized = frame[:expected_h, left:left + expected_w]
            method = "裁剪窗口边框"
        else:
            normalized = cv2.resize(
                frame,
                (expected_w, expected_h),
                interpolation=cv2.INTER_AREA,
            )
            method = "缩放适配"

        if not self._window_size_adapted:
            logger.info(
                f"[RouteRecorder] Auto normalized window from "
                f"{actual_w}x{actual_h} to {expected_w}x{expected_h} ({method})"
            )
            self.last_status = (
                f"正在录制：{self.args.new_map} · 已自动适配窗口 "
                f"{actual_w}×{actual_h}"
            )
            self._window_size_adapted = True
        return normalized

    def __init__(self, args):
        '''
        Init MapleStoryBot
        '''
        self.args = args # User arguments
        self.idx_routes = 0 # Index of route map
        self.fps = 0 # Frame per second
        self.is_first_frame = True # first frame flag
        self.is_enable = True
        self.is_terminated = False
        self.show_windows = not getattr(args, "ui_mode", False)
        self.continue_existing = getattr(args, "continue_existing", False)
        self.last_status = "尚未开始"
        self._save_route_requested = False
        self._clear_route_requested = False
        self._stop_requested = False
        self._route_dirty = False
        self._window_size_adapted = False
        self._last_window_size_warning = 0.0
        self._last_minimap_warning = 0.0
        self._last_player_marker_warning = 0.0
        self._motion_reference = None
        self._motion_inference_logged = False
        # Coordinate (top-left coordinate)
        self.loc_minimap = (0, 0) # minimap location on game screen
        self.loc_player = (0, 0) # player location on game screen
        self.loc_player_minimap = (0, 0) # player location on minimap
        self.loc_minimap_global = (0, 0) # minimap location on global map
        self.loc_player_global = (0, 0) # player location on global map
        self.loc_player_global_last = None # playeer location on global map last frame
        # Images
        self.frame = None # raw image
        self.img_frame = None # game window frame
        self.img_frame_debug = None # game window frame for visualization
        self.img_route = None # route map
        self.img_route_debug = None # route map for visualization
        self.img_minimap = None # minimap on game screen
        self.img_map = None # map
        # Timers
        self.t_last_frame = time.time() # Last frame timer, for fps calculation
        self.t_last_draw_blob = time.time() # Last draw blob timer

        # Load defautl yaml config
        cfg = load_yaml("config/config_default.yaml")
        # Override with platform config
        if is_mac():
            cfg = override_cfg(cfg, load_yaml("config/config_macOS.yaml"))
        # Override with the UI snapshot or a user customized config when available.
        config_path = getattr(args, "config_path", "")
        if not config_path:
            config_path = f"config/config_{args.cfg}.yaml"
        if os.path.exists(config_path):
            self.cfg = override_cfg(cfg, load_yaml(config_path))
        else:
            self.cfg = cfg

        # Parse color_code
        self.color_code = {
            tuple(map(int, k.split(','))): v
            for k, v in cfg["route"]["color_code"].items()
        }
        color_code_up_down = {
            tuple(map(int, k.split(','))): v
            for k, v in cfg["route"]["color_code_up_down"].items()
        }
        self.color_code.update(color_code_up_down) # Combine both dictionaries

        self.fps_limit = self.cfg["system"]["fps_limit_route_recorder"]

        # Create a new map directory or continue from an existing map.
        map_dir = os.path.join(MINIMAPS, args.new_map)
        if self.continue_existing:
            if not os.path.isdir(map_dir):
                raise FileNotFoundError(f"Map directory not found: {map_dir}")
            map_path = self.args.map or os.path.join(map_dir, "map.png")
            self.img_map = load_image(map_path)
            if self.img_map is None:
                raise FileNotFoundError(f"Map image not found: {map_path}")
            self.idx_routes = self._get_max_route_index(map_dir)
            logger.info(f"Continue map '{args.new_map}' from route{self.idx_routes + 1}")
        else:
            if os.path.exists(map_dir):
                if getattr(args, "ui_mode", False):
                    raise FileExistsError(f"Map directory already exists: {map_dir}")
                user_input = input(
                    f"[Warning] Directory '{map_dir}' already exists. Replace it? (y/n): "
                ).strip().lower()
                if user_input == 'y':
                    shutil.rmtree(map_dir)
                    logger.info(f"Removed existing directory: {map_dir}")
                else:
                    sys.exit(0)
            os.makedirs(map_dir)
            logger.info(f"Created new directory: {map_dir}")
            if self.args.map != '':
                self.img_map = load_image(self.args.map)

        # Start keyboard listener thread
        self.kb = KeyBoardListener(self.cfg, is_autobot=False)
        self.kb.register_func_key_handler('f1', self.toggle_pause)
        self.kb.register_func_key_handler('f2', self.request_save_route)
        self.kb.register_func_key_handler('f3', self.request_clear_route)
        self.kb.register_func_key_handler('f4', self.request_stop)

        # Start game window capturing thread
        logger.info("Waiting for game window to activate, please click on game window")
        # Capture the window itself instead of its on-screen rectangle. MSS
        # records whichever app is covering the game, which makes minimap
        # detection fail whenever this UI is visible over the game window.
        if is_mac():
            self.capture = GameWindowCapturor(self.cfg)
        else:
            self.capture = GameWindowCapturor(
                self.cfg,
                backend="windows_capture",
            )
        self.last_status = f"正在录制：{args.new_map}"

    @staticmethod
    def _get_max_route_index(map_dir):
        max_index = 0
        for path in glob.glob(os.path.join(map_dir, "route*.png")):
            match = re.search(r"route_?(\d+)", os.path.basename(path), re.IGNORECASE)
            if match:
                max_index = max(max_index, int(match.group(1)))
        return max_index

    def toggle_pause(self):
        self.is_enable = not self.is_enable
        self.kb.is_pressed_func_key[0] = False
        self.last_status = "录制已暂停" if not self.is_enable else f"正在录制：{self.args.new_map}"
        logger.info(f"Route recording enabled: {self.is_enable}")

    def request_save_route(self):
        self._save_route_requested = True
        self.kb.is_pressed_func_key[1] = False

    def request_clear_route(self):
        self._clear_route_requested = True
        self.kb.is_pressed_func_key[2] = False

    def request_stop(self):
        self._stop_requested = True
        self.kb.is_pressed_func_key[3] = False

    def _new_route_canvas(self):
        if self.img_map is None:
            return None
        return self.remove_color_code_pixels(self.img_map.copy())

    def save_current_route(self):
        if self.img_route is None:
            return None
        if not self._route_dirty:
            self.last_status = "当前路线为空，未保存"
            return None
        action_to_color = {value: key for key, value in self.color_code.items()}
        goal_rgb = action_to_color.get("none none goal")
        if goal_rgb is not None:
            goal_bgr = (goal_rgb[2], goal_rgb[1], goal_rgb[0])
            cv2.circle(
                self.img_route,
                self.loc_player_global,
                radius=2,
                color=goal_bgr,
                thickness=-1,
            )
        map_dir = os.path.join(MINIMAPS, self.args.new_map)
        next_index = max(self.idx_routes + 1, self._get_max_route_index(map_dir) + 1)
        out_path = os.path.join(map_dir, f"route{next_index}.png")
        cv2.imwrite(out_path, self.img_route)
        self.idx_routes = next_index
        self.img_route = self._new_route_canvas()
        self.img_route_debug = self.img_route.copy()
        self.loc_player_global_last = None
        self._route_dirty = False
        self.last_status = f"已保存 route{next_index}，继续录制下一条路线"
        logger.info(f"Save route image to {out_path}")
        return out_path

    def clear_current_route(self):
        self.img_route = self._new_route_canvas()
        if self.img_route is not None:
            self.img_route_debug = self.img_route.copy()
        self.loc_player_global_last = None
        self._route_dirty = False
        self.last_status = "已清空当前未保存路线"
        logger.info("Cleared current route")

    def stop(self):
        if self.is_terminated:
            return
        if self._route_dirty:
            self.save_current_route()
        if self.img_map is not None:
            map_path = os.path.join(MINIMAPS, self.args.new_map, "map.png")
            cv2.imwrite(map_path, self.img_map)
            logger.info(f"Save map image to {map_path}")
        self.is_terminated = True
        self.last_status = "录制结束"
        if self.kb is not None:
            self.kb.stop()
        if self.capture is not None:
            self.capture.stop()
        if self.show_windows:
            cv2.destroyAllWindows()

    def ensure_img_map_capacity(self, x, y, h, w):
        '''
        Ensure that self.img_map is large enough to contain the region defined by (x, y, h, w).
        Always add at least "map_padding" when expanding in any direction.
        '''
        map_h, map_w = self.img_map.shape[:2]
        pad = self.cfg["route_recoder"]["map_padding"]

        # Compute required expansion margins
        expand_top = pad - y if y < pad else 0
        expand_left = pad - x if x < pad else 0
        expand_bottom = y + h + pad - map_h if y + h + pad > map_h else 0
        expand_right = x + w + pad - map_w if x + w + pad > map_w else 0
        expand_top = max(0, expand_top)
        expand_left = max(0, expand_left)
        expand_bottom = max(0, expand_bottom)
        expand_right = max(0, expand_right)
        # If no expansion needed, return
        if expand_top == 0 and expand_bottom == 0 and expand_left == 0 and expand_right == 0:
            return

        # Create new canvas and paste old image
        new_h = map_h + expand_top + expand_bottom
        new_w = map_w + expand_left + expand_right
        new_map = np.zeros((new_h, new_w, 3), dtype=np.uint8)

        new_map[expand_top:expand_top + map_h, expand_left:expand_left + map_w] = self.img_map
        self.img_map = new_map

        if self.img_route is not None:
            route_h, route_w = self.img_route.shape[:2]
            expanded_route = np.zeros((new_h, new_w, 3), dtype=np.uint8)
            expanded_route[
                expand_top:expand_top + route_h,
                expand_left:expand_left + route_w,
            ] = self.img_route
            self.img_route = expanded_route
            self.img_route_debug = expanded_route.copy()

        if self.loc_player_global_last is not None:
            self.loc_player_global_last = (
                self.loc_player_global_last[0] + expand_left,
                self.loc_player_global_last[1] + expand_top,
            )

        # Also update all global coordinates that depend on the map (optional)
        self.loc_minimap_global = (
            self.loc_minimap_global[0] + expand_left,
            self.loc_minimap_global[1] + expand_top
        )

    def remove_color_code_pixels(self, img):
        """
        Set all pixels in self.img_map to black if they match any color in color_code (assumed RGB).
        """
        for rgb in self.color_code.keys():
            bgr = (rgb[2], rgb[1], rgb[0])  # Convert RGB → BGR
            mask = np.all(img == bgr, axis=2)
            img[mask] = (0, 0, 0)
        return img

    @staticmethod
    def infer_motion_action(previous, current, minimum_distance=2):
        """Infer arrow movement when the global key listener misses a press."""
        if previous is None or current is None:
            return ""
        dx = int(current[0]) - int(previous[0])
        dy = int(current[1]) - int(previous[1])
        if max(abs(dx), abs(dy)) < minimum_distance:
            return ""
        if abs(dx) >= abs(dy):
            return "right none none" if dx > 0 else "left none none"
        return "none down none" if dy > 0 else "none up none"

    def update_minimap(self):
        '''
        update_minimap
        '''

    def run_once(self):
        '''
        Process with one game window frame
        '''
        if self._stop_requested:
            self.stop()
            return 1

        # Get lastest game screen frame buffer
        img_frame = self.get_img_frame()
        if img_frame is None:
            return -1 # Wait for game window to be ready
        else:
            self.img_frame = img_frame

        # Image for debug use
        self.img_frame_debug = self.img_frame.copy()

        # Get minimap from game window
        if self.is_first_frame:
            minimap_result = get_minimap_loc_size(self.img_frame)
            if minimap_result is None:
                self.last_status = "等待识别游戏小地图"
                now = time.monotonic()
                if now - self._last_minimap_warning >= 2.0:
                    logger.warning(
                        "[RouteRecorder] Minimap not detected; no route points "
                        "can be recorded from this frame."
                    )
                    self._last_minimap_warning = now
                return -1
            x, y, w, h = minimap_result
            # Discard 1 pixel boundary of the minimap
            x += 1
            y += 1
            w -= 2
            h -= 2
            self.loc_minimap = (x, y)
            self.img_minimap = self.img_frame[y:y+h, x:x+w]
        else:
            x, y = self.loc_minimap
            h, w = self.img_minimap.shape[:2]
            self.img_minimap = self.img_frame[y:y+h, x:x+w]

        # Replace black pixels (0, 0, 0) with (1, 1, 1)
        black_mask = np.all(self.img_minimap == [0, 0, 0], axis=-1)
        self.img_minimap[black_mask] = [1, 1, 1]

        # Get player location on minimap
        loc_player_minimap = get_player_location_on_minimap(
            self.img_minimap,
            minimap_player_color=self.cfg["minimap"]["player_color"],
        )
        player_marker_detected = loc_player_minimap is not None
        if player_marker_detected:
            self.loc_player_minimap = loc_player_minimap
        else:
            now = time.monotonic()
            if now - self._last_player_marker_warning >= 2.0:
                logger.warning(
                    "[RouteRecorder] Player marker not detected on minimap; "
                    "this frame is ignored."
                )
                self._last_player_marker_warning = now

        # Update map
        if self.is_first_frame:
            # copy minimap to map
            created_new_map = self.img_map is None
            if self.img_map is None:
                self.img_map = self.img_minimap.copy()
                pad = self.cfg["route_recoder"]["map_padding"]
                self.img_map = cv2.copyMakeBorder(
                    self.img_map,
                    top=pad, bottom=pad, left=pad, right=pad,
                    borderType=cv2.BORDER_CONSTANT,
                    value=(0, 0, 0)  # Black padding
                )

            # Replace player "yellow" dot to black on map
            self.replace_color_on_map(
                (55, 40, 80),
                (60, 100, 100)
            )
            # Replace other player "red" dot to black on map
            self.replace_color_on_map((0, 80, 80),
                                      (5, 100, 100))

            # Update route
            self.img_route = self.remove_color_code_pixels(self.img_map.copy())
            self.img_route_debug = self.img_route.copy()
            if created_new_map:
                map_path = os.path.join(MINIMAPS, self.args.new_map, "map.png")
                if not cv2.imwrite(map_path, self.img_map):
                    raise OSError(f"无法保存地图截图：{map_path}")
                self.last_status = (
                    f"正在录制：{self.args.new_map} · 已创建 map.png / route1"
                )
                logger.info(f"Saved initial minimap to {map_path}")

        else:
            # Perform template matching to find where the current minimap fits in the global map
            self.loc_minimap_global, score, _ = match_minimap_on_map(
                self.img_map,
                self.img_minimap,
                last_result=self.loc_minimap_global,
                mask=self.get_minimap_match_mask(),
            )
            x, y = self.loc_minimap_global
            h, w = self.img_minimap.shape[:2]
            # Ensure img_map is big enough to fit the newly explored region
            if not self.continue_existing:
                self.ensure_img_map_capacity(x, y, h, w)
            x, y = self.loc_minimap_global

            # Don't copy pixel near player
            player_yellow_dot_radius = 5
            px, py = self.loc_player_minimap
            h, w = self.img_minimap.shape[:2]
            x_min = max(0, px - player_yellow_dot_radius)
            x_max = min(w, px + player_yellow_dot_radius)
            y_min = max(0, py - player_yellow_dot_radius)
            y_max = min(h, py + player_yellow_dot_radius)
            # Apply the black color mask to mask player yellow dot
            self.img_minimap[y_min:y_max, x_min:x_max] = (0, 0, 0)

            # Update map
            if self.args.map == '':
                map_slice = self.img_map[y:y+h, x:x+w]
                black_mask = np.all(map_slice == [0, 0, 0], axis=2)
                map_slice[black_mask] = self.img_minimap[black_mask]

            # Replace other player "red" dot to black on map
            self.replace_color_on_map((0, 78, 78),
                                      (5, 100, 100))

        if self.show_windows:
            cv2.imshow("Map", self.img_map)
        self.img_route_debug = self.img_route.copy()

        # Get player location on global map
        self.loc_player_global = self.get_player_location_on_global_map()

        # Determine which color code to use based on user input
        action = ""
        is_draw_blob = False
        key_press = self.kb.key_pressing
        jump_key = str(self.cfg["key"].get("jump", "space")).lower()
        teleport_key = str(self.cfg["key"].get("teleport", "e")).lower()
        if jump_key and jump_key in key_press:
            if "left" in key_press:
                action = "left none jump"
            elif "right" in key_press:
                action = "right none jump"
            elif "down" in key_press:
                action = "none down jump"
            else:
                action = "none none jump"
            is_draw_blob = True
        elif teleport_key and teleport_key in key_press:
            if "left" in key_press:
                action = "left none teleport"
            elif "right" in key_press:
                action = "right none teleport"
            elif "down" in key_press:
                action = "none down teleport"
            elif "up" in key_press:
                action = "none up teleport"
            else:
                action = ""
            is_draw_blob = True
        elif "up" in key_press:
            action = "none up none"
        elif "down" in key_press:
            action = "none down none"
        elif "left" in key_press:
            action = "left none none"
        elif "right" in key_press:
            action = "right none none"
        else:
            action = ""

        # pynput can miss arrow presses while the embedded recorder UI changes
        # focus. The minimap still provides an independent movement signal, so
        # use it as a conservative fallback for ordinary walking/climbing.
        if action == "" and player_marker_detected:
            action = self.infer_motion_action(
                self._motion_reference,
                self.loc_player_global,
            )
            if action and not self._motion_inference_logged:
                logger.info(
                    "[RouteRecorder] Keyboard movement was not observed; "
                    "recording movement inferred from the minimap."
                )
                self._motion_inference_logged = True
        if action or self._motion_reference is None:
            self._motion_reference = self.loc_player_global

        # Update route image
        if self.is_enable and action != "":
            # Get color from action
            dict_action_to_color = {v: k for k, v in self.color_code.items()}
            color_rgb = dict_action_to_color.get(action, None)
            color_bgr = (color_rgb[2], color_rgb[1], color_rgb[0])

            # Draw a line from the last position to the current one (if available)
            px, py = self.loc_player_global
            if is_draw_blob:
                dt = time.time() - self.t_last_draw_blob
                if dt > self.cfg["route_recoder"]["blob_cooldown"]:
                    # Draw a small filled circle at current position
                    cv2.circle(self.img_route,
                            (px, py),
                            radius=2,
                            color=color_bgr,
                            thickness=-1)  # filled circle
                    self.t_last_draw_blob = time.time()
                    self.loc_player_global_last = None
                    self._route_dirty = True
            else:
                if self.loc_player_global_last is None:
                    px_last, py_last = self.loc_player_global
                else:
                    px_last, py_last = self.loc_player_global_last
                cv2.line(self.img_route,
                        (px_last, py_last),
                        (px     , py),
                        color=color_bgr,
                        thickness=1)
                self.loc_player_global_last = self.loc_player_global
                self._route_dirty = True

        if self._clear_route_requested:
            self._clear_route_requested = False
            self.clear_current_route()
        if self._save_route_requested:
            self._save_route_requested = False
            self.save_current_route()
        if self._stop_requested:
            self.stop()
            return 1

        #####################
        ### Debug Windows ###
        #####################
        # Print text on debug image
        self.update_info_on_img_frame_debug()

        # Show debug image on window
        self.update_img_frame_debug()

        # Resize img_route_debug for better visualization
        self.img_route_debug = cv2.resize(
                    self.img_route_debug, (0, 0),
                    fx=self.cfg["minimap"]["debug_window_upscale"],
                    fy=self.cfg["minimap"]["debug_window_upscale"],
                    interpolation=cv2.INTER_NEAREST)
        if self.show_windows:
            cv2.imshow("Route Map Debug", self.img_route_debug)

        # Enable cached location since second frame
        self.is_first_frame = False
        return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Argument to specify map name
    parser.add_argument(
        '--new_map',
        type=str,
        default='new_map',
        help='Specify the new map name'
    )

    parser.add_argument(
        '--cfg',
        type=str,
        default='custom',
        help='Choose customized config yaml file in config/'
    )

    parser.add_argument(
        '--map',
        type=str,
        default='',
        help='use this map instead of creating a new one'
    )

    try:
        routeRecorder = RouteRecorder(parser.parse_args())
    except Exception as e:
        logger.error(f"RouteRecorder Init failed: {e}")
        sys.exit(1)
    else:
        while not routeRecorder.is_terminated:
            t_start = time.time()

            # Process one game window frame
            routeRecorder.run_once()

            # Exit if 'q' is pressed
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                routeRecorder.stop()
                break

            # Cap FPS to save system resource
            frame_duration = time.time() - t_start
            target_duration = 1.0 / routeRecorder.fps_limit
            if frame_duration < target_duration:
                time.sleep(target_duration - frame_duration)

        cv2.destroyAllWindows()
