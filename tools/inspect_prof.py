# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
text = p.read_text(encoding="utf-8")
print("len", len(text))
print("has _ensure_builtin_profiles", "_ensure_builtin_profiles" in text)
print("has _sword_profile", "_sword_profile" in text)
# show around _load and methods
lines = text.splitlines()
for i, line in enumerate(lines, 1):
    if "_ensure_builtin" in line or "_sword_profile" in line or "def _load" in line or "class Profession" in line:
        print(f"{i}: {line}")
# print from line 90 to 250
print("\n===== 90-280 =====")
for i in range(89, min(280, len(lines))):
    print(f"{i+1}: {lines[i]}")
