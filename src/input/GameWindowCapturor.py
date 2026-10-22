'''
Execute this script:
python mapleStoryAutoLevelUp.py --map cloud_balcony --monster brown_windup_bear,pink_windup_bear
'''
# Standard import
import time
import threading
import ctypes
from ctypes import wintypes

# Libarary Import
from windows_capture import WindowsCapture, Frame, InternalCaptureControl
import cv2
import mss
import numpy as np
import win32gui

# local import
from src.utils.logger import logger
from src.utils.common import get_game_window_title_by_token, load_image, resize_window

class GameWindowCapturor:
    '''
    GameWindowCapturor
    '''
    def __init__(self, cfg, test_image_name=None, backend="windows_capture"):
        self.cfg = cfg
        self.frame = None
        self.lock = threading.Lock()
        self.frame_ready = threading.Event()
        self.is_terminated = False
        self.backend = backend
        self.fps = 0
        self.fps_limit = cfg["system"]["fps_limit_window_capturor"]
        self.t_last_run = 0.0
        self.capture_control = None
        self.capture = None
        self.capture_thread = None
        self.capture_error = None
        self.window_title = ""
        self.window_hwnd = 0
        self.returns_client_frame = True

        # If use test image as input, disable the whole capture thread
        if test_image_name is not None:
            self.frame = load_image(f"test/{test_image_name}.png")
            self.frame_ready.set()
            return

        # Get game window title
        self.window_title = get_game_window_title_by_token(cfg["game_window"]["title"])
        if self.window_title is None:
            raise RuntimeError(
                f"[GameWindowCapturor] Unable to find window title containing: {cfg['game_window']['title']}"
            )
        logger.info(f"[GameWindowCapturor] Found game window title: {self.window_title}")

        self.window_hwnd = win32gui.FindWindow(None, self.window_title)
        if self.window_hwnd == 0:
            raise RuntimeError(
                f"[GameWindowCapturor] Unable to resolve game window handle: {self.window_title}"
            )

        if cfg["game_window"].get("resize_on_start", False):
            outer_height, outer_width = cfg["game_window"].get(
                "outer_size", (759, 1296)
            )
            resize_window(
                self.window_title,
                width=outer_width,
                height=outer_height,
            )

        if self.backend == "mss":
            self.capture_thread = threading.Thread(
                target=self._run_mss_capture,
                name="MapleStoryMSSCapture",
                daemon=True,
            )
            self.capture_thread.start()
            logger.info("[GameWindowCapturor] MSS backend started")
            return

        # Create capture handler
        # Use HWND instead of window_name. The capture library treats names as
        # substring matches, so a browser tab containing the game title can be
        # selected instead of the actual client.
        self.capture = WindowsCapture(
            window_hwnd=self.window_hwnd,
            minimum_update_interval=max(1, round(1000 / self.fps_limit)),
        )
        self.capture.event(self.on_frame_arrived)
        self.capture.event(self.on_closed)

        # Start capturing thread
        self.capture_control = self.capture.start_free_threaded()

        logger.info("[GameWindowCapturor] Init done")

    def _run_mss_capture(self):
        """Capture the target window without blocking the recorder QThread."""
        hwnd = self.window_hwnd
        if hwnd == 0:
            logger.error(f"[GameWindowCapturor] Window disappeared: {self.window_title}")
            return

        try:
            with mss.mss() as capture:
                while not self.is_terminated:
                    client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
                    _, _, client_width, client_height = win32gui.GetClientRect(hwnd)
                    if client_width <= 0 or client_height <= 0:
                        time.sleep(0.1)
                        continue

                    screenshot = capture.grab({
                        "left": client_left,
                        "top": client_top,
                        "width": client_width,
                        "height": client_height,
                    })
                    frame = np.asarray(screenshot).copy()
                    with self.lock:
                        self.frame = frame
                    self.frame_ready.set()
                    self.limit_fps()
        except Exception as error:
            self.capture_error = error
            self.frame_ready.set()
            logger.error(f"[GameWindowCapturor] MSS capture failed: {error}")
        finally:
            logger.info("[GameWindowCapturor] MSS backend terminated")

    def on_frame_arrived(self, frame: Frame,
                         capture_control: InternalCaptureControl):
        '''
        Frame arrived callback: store frame into buffer with lock.
        '''
        # frame_buffer is backed by a mapped native texture whose lifetime ends
        # when this callback returns. Keep an owned copy for the processing loop.
        frame_copy = np.asarray(frame.frame_buffer).copy()
        with self.lock:
            self.frame = frame_copy
        self.frame_ready.set()

        now = time.time()
        if self.t_last_run:
            self.fps = round(1.0 / max(now - self.t_last_run, 1e-6))
        self.t_last_run = now

    def on_closed(self):
        '''
        Capture closed callback.
        '''
        self.capture_error = RuntimeError("Windows capture session closed")
        self.frame_ready.set()
        logger.warning("[GameWindowCapturor] closed.")
        cv2.destroyAllWindows()

    def wait_for_frame(self, timeout=3.0):
        """Wait until the capture backend produces its first owned frame."""
        self.frame_ready.wait(timeout)
        return self.get_frame()

    def get_frame(self):
        '''
        Safely get latest game window frame.
        '''
        with self.lock:
            if self.capture_error is not None:
                raise RuntimeError(
                    f"[GameWindowCapturor] {self.backend} capture failed: "
                    f"{self.capture_error}"
                )
            if self.frame is None:
                return None
            frame = self.frame.copy()

        if self.backend == "windows_capture":
            frame = self._crop_window_frame_to_client(frame)
        if frame.ndim == 3 and frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def _crop_window_frame_to_client(self, frame):
        """Remove borders/title bar using the real Windows client geometry."""
        try:
            window_rect = win32gui.GetWindowRect(self.window_hwnd)
            extended_rect = self._get_extended_frame_bounds()
            client_rect = win32gui.GetClientRect(self.window_hwnd)
            client_origin = win32gui.ClientToScreen(self.window_hwnd, (0, 0))
            capture_bounds = self.select_capture_bounds(
                frame.shape[:2], window_rect, extended_rect
            )
            return self.crop_frame_to_client_geometry(
                frame, capture_bounds, client_origin, client_rect[2:4]
            )
        except Exception as error:
            logger.warning(
                f"[GameWindowCapturor] Unable to crop client area: {error}"
            )
            return frame

    def _get_extended_frame_bounds(self):
        """Return the DWM-visible window bounds used by Windows Capture."""
        rect = wintypes.RECT()
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            self.window_hwnd,
            9,  # DWMWA_EXTENDED_FRAME_BOUNDS
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
        if result != 0:
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)

    @staticmethod
    def select_capture_bounds(frame_shape, window_rect, extended_rect=None):
        """Choose the Windows bounds whose size matches the WGC frame."""
        frame_height, frame_width = frame_shape
        candidates = [window_rect]
        if extended_rect is not None:
            candidates.append(extended_rect)

        def size_error(rect):
            left, top, right, bottom = rect
            return abs((right - left) - frame_width) + abs(
                (bottom - top) - frame_height
            )

        return min(candidates, key=size_error)

    @staticmethod
    def crop_frame_to_client_geometry(frame, window_rect, client_origin, client_size):
        """Crop a captured outer-window frame to its client area."""
        left, top, right, bottom = window_rect
        outer_width = right - left
        outer_height = bottom - top
        client_width, client_height = client_size
        if outer_width <= 0 or outer_height <= 0:
            return frame

        frame_height, frame_width = frame.shape[:2]
        scale_x = frame_width / outer_width
        scale_y = frame_height / outer_height
        x0 = round((client_origin[0] - left) * scale_x)
        y0 = round((client_origin[1] - top) * scale_y)
        x1 = x0 + round(client_width * scale_x)
        y1 = y0 + round(client_height * scale_y)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(frame_width, x1), min(frame_height, y1)
        if x1 <= x0 or y1 <= y0:
            return frame
        return frame[y0:y1, x0:x1].copy()

    def stop(self):
        '''
        Stop capturing thread
        '''
        self.is_terminated = True
        self.frame_ready.set()
        if self.capture_control is not None:
            self.capture_control.stop()
        if (
            self.capture_thread is not None
            and self.capture_thread.is_alive()
            and self.capture_thread is not threading.current_thread()
        ):
            self.capture_thread.join(timeout=1.0)
        logger.info("[GameWindowCapturor] Terminated")

    def limit_fps(self):
        '''
        Limit FPS
        '''
        # If the loop finished early, sleep to maintain target FPS
        target_duration = 1.0 / self.fps_limit  # seconds per frame
        frame_duration = time.time() - self.t_last_run
        if frame_duration < target_duration:
            time.sleep(target_duration - frame_duration)

        # Update FPS
        self.fps = round(1.0 / (time.time() - self.t_last_run))
        self.t_last_run = time.time()
        # logger.info(f"FPS = {self.fps}")
