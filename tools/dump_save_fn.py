# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
lines = (ROOT / "src" / "ui" / "ui.py").read_text(encoding="utf-8").splitlines()
for a,b in [(580,620),(1480,1540),(2280,2350),(2420,2530)]:
    print(f"\n===== {a}-{b} =====")
    for j in range(a-1, min(b, len(lines))):
        print(f"{j+1}: {lines[j]}")

print("\n===== tommy =====")
print((ROOT/"config/config_tommy.yaml").read_text(encoding="utf-8"))
print("===== custom size", (ROOT/"config/config_custom.yaml").stat().st_size)
print(repr((ROOT/"config/config_custom.yaml").read_text(encoding="utf-8")[:200]))

# save_yaml impl
common = (ROOT/"src/utils/common.py").read_text(encoding="utf-8")
idx = common.find("def save_yaml")
print("\n===== save_yaml =====")
print(common[idx:idx+800])
idx2 = common.find("def get_cfg_diff")
print("\n===== get_cfg_diff start =====")
print(common[idx2:idx2+600])
