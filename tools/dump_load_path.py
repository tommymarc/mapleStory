# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ui = (ROOT / "src" / "ui" / "ui.py").read_text(encoding="utf-8")
lines = ui.splitlines()
# find path_cfg_custom assignments and load_config
for i, line in enumerate(lines):
    if "path_cfg_custom" in line or "def load_config" in line or "config_tommy" in line or "config_custom" in line:
        start = max(0, i-1)
        end = min(len(lines), i+6)
        print(f"\n--- around {i+1} ---")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}")

# load_yaml empty
import sys
sys.path[:0] = [str(ROOT), str(ROOT/"src")]
from src.utils.common import load_yaml
p = ROOT/"config/config_custom.yaml"
print("\nload empty custom:")
try:
    print(repr(load_yaml(str(p))))
except Exception as e:
    print("ERR", type(e), e)

# common load_yaml
c = (ROOT/"src/utils/common.py").read_text(encoding="utf-8")
idx = c.find("def load_yaml")
print(c[idx:idx+500])
