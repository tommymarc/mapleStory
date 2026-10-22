# -*- coding: utf-8 -*-
from pathlib import Path
import os
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
cands = [
    ROOT / "config" / "config_professions.yaml",
    ROOT / "dist" / "config" / "config_professions.yaml",
    Path(os.environ.get("APPDATA", "")) / ".maplebot" / "config_professions.yaml",
    Path(os.environ.get("APPDATA", "")) / ".maplebot" / "config" / "config_professions.yaml",
]
# also search
for p in Path(os.environ.get("APPDATA", "C:/Users/Administrator/AppData/Roaming")).rglob("config_professions.yaml"):
    cands.append(p)
for p in ROOT.rglob("config_professions.yaml"):
    cands.append(p)
seen = set()
for p in cands:
    try:
        rp = str(p.resolve())
    except Exception:
        rp = str(p)
    if rp in seen:
        continue
    seen.add(rp)
    exists = p.exists()
    print("===", rp, "exists=", exists)
    if exists:
        t = p.read_text(encoding="utf-8")
        print("selected line:", [ln for ln in t.splitlines() if "selected" in ln or "剑客" in ln or "战士" in ln][:8])
        print("keys sample:", t[:200].replace("\n"," | "))
