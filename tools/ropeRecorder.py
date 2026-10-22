"""CLI entry for rope recording — implementation lives in src.utils.rope_recorder."""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from src.utils.rope_recorder import RopeRecorder, load_recorder_cfg  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Record one-time rope climbs for smart_patrol")
    parser.add_argument(
        "--map",
        required=True,
        help="Map id, e.g. duoluozhuyi-xia or duoluozhuyi-shang",
    )
    parser.add_argument("--cfg", default="tommy", help="config_* name (default tommy)")
    parser.add_argument("--no-window", action="store_true", help="Disable OpenCV preview")
    args = parser.parse_args()
    cfg = load_recorder_cfg(args.cfg)
    rec = RopeRecorder(args.map, cfg)
    rec.run(show_window=not args.no_window)


if __name__ == "__main__":
    main()
