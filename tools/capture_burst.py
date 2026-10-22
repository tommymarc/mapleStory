# -*- coding: utf-8 -*-
"""Burst-capture game window + bot window; save several frames for miss analysis."""
from pathlib import Path
import time, ctypes
from ctypes import wintypes
import cv2, numpy as np

OUT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\_live_diag\burst")
OUT.mkdir(parents=True, exist_ok=True)
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

def list_windows():
    out = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value or ""
        if ("怀旧" in title) or ("MapleStory Auto" in title) or ("冒险岛怀旧" in title):
            r = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if w > 200 and h > 200:
                out.append((title, r.left, r.top, r.right, r.bottom, w, h))
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out

def grab(left, top, right, bottom):
    w, h = right - left, bottom - top
    hwnd_desk = user32.GetDesktopWindow()
    hdc = user32.GetWindowDC(hwnd_desk)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, left, top, 0x00CC0020)
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
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
    buf = (ctypes.c_ubyte * (w * h * 4))()
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(hwnd_desk, hdc)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

wins = list_windows()
print("wins", [(t, w, h) for t,_,_,_,_,w,h in wins])
game = next((x for x in wins if "怀旧" in x[0] or "Maple" not in x[0]), None)
bot = next((x for x in wins if "Auto" in x[0]), None)
if game is None and wins:
    game = max(wins, key=lambda x: x[5]*x[6])
for i in range(5):
    if game:
        t,l,tp,r,b,w,h = game
        img = grab(l,tp,r,b)
        p = OUT / f"game_{i}.png"
        cv2.imencode(".png", img)[1].tofile(str(p))
        print("saved", p, img.shape)
    if bot and i == 0:
        t,l,tp,r,b,w,h = bot
        img = grab(l,tp,r,b)
        p = OUT / "bot_ui.png"
        cv2.imencode(".png", img)[1].tofile(str(p))
        print("saved bot", p, img.shape)
    time.sleep(0.35)
print("done")
