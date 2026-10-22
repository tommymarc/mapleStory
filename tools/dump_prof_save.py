# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp\src\ui\profession_config.py")
lines = p.read_text(encoding="utf-8").splitlines()
# find class and _save
for i, line in enumerate(lines):
    if "class " in line and ("Profession" in line or "Dialog" in line or "Tab" in line):
        print(f"{i+1}: {line}")
    if "def _save" in line or "保存配置" in line or "def save" in line:
        print(f"{i+1}: {line}")

print("\n===== 700-820 =====")
for j in range(699, min(820, len(lines))):
    print(f"{j+1}: {lines[j]}")
print("\n===== 900-1020 =====")
for j in range(899, min(1020, len(lines))):
    print(f"{j+1}: {lines[j]}")
