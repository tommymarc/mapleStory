# -*- coding: utf-8 -*-
"""Merge dual-nametag + A config into config_tommy.yaml without wiping other keys."""
from __future__ import annotations
from pathlib import Path
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required")

ROOT = Path(__file__).resolve().parents[1]
# tools/dual_nametag_payload -> parents[1] = repo
for cand in [Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2], Path.cwd()]:
    if (cand / "config" / "config_tommy.yaml").exists():
        ROOT = cand
        break

path = ROOT / "config" / "config_tommy.yaml"
data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
nt = data.setdefault("nametag", {})
nt["enable"] = True
nt.setdefault("name", "日丁")
nt.setdefault("layers", 3)
nt["dual_template"] = True
nt["verify_on_reacquire"] = True
nt["verify_diff_thres"] = 0.28
nt["scan_every_n_frames"] = 3
nt["search_margin"] = 200
nt["occluded_diff_thres"] = 0.40
nt["occluded_plate_support"] = 0.22
# keep existing offset / reacquire if present
path.write_text(
    yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
    encoding="utf-8",
)
print("updated", path)
print("nametag:", nt)
