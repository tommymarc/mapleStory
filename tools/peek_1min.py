from pathlib import Path
ROOT = Path(r"C:\Users\Administrator\Desktop\应用管理\Mapple\MapleStoryAutoLevelUp")
log = ROOT / "_live_diag" / "combat_1min_run.log"
print("log_exists", log.exists(), "size", log.stat().st_size if log.exists() else 0)
if log.exists():
    print(log.read_text(encoding="utf-8", errors="replace")[-2500:])
