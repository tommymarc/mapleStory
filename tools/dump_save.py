# -*- coding: utf-8 -*-
from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
ui = (ROOT / "src" / "ui" / "ui.py").read_text(encoding="utf-8")
lines = ui.splitlines()
for i, line in enumerate(lines):
    if any(k in line for k in ("保存", "save_config", "save_yaml", "on_save", "btn_save", "Save Config", "写入", "config_custom", "config_tommy")):
        print(f"{i+1}: {line}")

print("\n--- file sizes ---")
for rel in ["config/config_tommy.yaml", "dist/config/config_tommy.yaml", "config/config_default.yaml", "config/config_custom.yaml"]:
    p = ROOT / rel
    if p.exists():
        print(rel, p.stat().st_size, "bytes", "lines", len(p.read_text(encoding="utf-8", errors="ignore").splitlines()))

# list backups
for p in (ROOT / "config").glob("*tommy*"):
    print("config", p.name, p.stat().st_size)
for p in (ROOT / "dist" / "config").glob("*tommy*"):
    print("dist", p.name, p.stat().st_size)
