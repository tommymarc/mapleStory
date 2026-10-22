# -*- coding: utf-8 -*-
"""Capture MapleStory / bot windows and summarize nametag/monster debug overlays if present."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from pathlib import Path
import time

import cv2
import numpy as np

OUT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\_live_diag")
OUT.mkdir(parents=True, exist_ok=True)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def list_windows():
    EnumWindows = user32.EnumWindows
    GetWindowTextW = user32.GetWindowTextW
    IsWindowVisible = user32.IsWindowVisible
    GetWindowRect = user32.GetWindowRect
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    out = []

    def cb(hwnd, lparam):
        if not IsWindowVisible(hwnd):
            return True
        n = GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value or ""
        keys = ("Maple", "冒险", "挂机", "Auto", "MapleStory", "监控", "野猪", "日丁")
        if any(k in title for k in keys) or "maple" in title.lower():
            r = RECT()
            GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 80 and h > 80:
                out.append((title, r.left, r.top, r.right, r.bottom, int(hwnd), w, h))
        return True

    EnumWindows(WNDENUMPROC(cb), 0)
    return out


def grab_rect(left, top, right, bottom):
    w, h = right - left, bottom - top
    hwnd_desk = user32.GetDesktopWindow()
    hdc = user32.GetWindowDC(hwnd_desk)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, left, top, 0x00CC0020)
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd_desk, hdc)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)


def main():
    wins = list_windows()
    print("FOUND", len(wins))
    for i, (t, l, tp, r, b, hwnd, w, h) in enumerate(wins):
        print(f"{i}: {t!r} {w}x{h} @({l},{tp})")
    # Also full virtual screen grab
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print("VIRTUAL", vx, vy, vw, vh)
    desk = grab_rect(vx, vy, vx + vw, vy + vh)
    desk_path = OUT / "desktop_full.png"
    cv2.imencode(".png", desk)[1].tofile(str(desk_path))
    print("saved", desk_path)

    for i, (t, l, tp, r, b, hwnd, w, h) in enumerate(wins[:6]):
        try:
            img = grab_rect(l, tp, r, b)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in t)[:40]
            path = OUT / f"win_{i}_{safe}_{w}x{h}.png"
            cv2.imencode(".png", img)[1].tofile(str(path))
            print("saved", path)
        except Exception as e:
            print("fail", t, e)

    # Prefer largest maple-like window for a second capture after 0.4s
    time.sleep(0.4)
    if wins:
        wins2 = sorted(wins, key=lambda x: x[6] * x[7], reverse=True)
        t, l, tp, r, b, hwnd, w, h = wins2[0]
        img = grab_rect(l, tp, r, b)
        path = OUT / "primary_window.png"
        cv2.imencode(".png", img)[1].tofile(str(path))
        print("primary", t, path)


if __name__ == "__main__":
    main()
