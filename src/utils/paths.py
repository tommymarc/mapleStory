"""Central resource path helpers.

Dev and frozen exe both chdir to the application root (project root or dist/),
then load static game resources from assets/.

User-editable map data (ropes.yaml / patrol.yaml) is stored under
``~/.maplebot/maps/<map>/`` so rebuilds of dist/assets do not wipe recordings.
"""

from __future__ import annotations

import os
from pathlib import Path

ASSETS = "assets"

MINIMAPS = os.path.join(ASSETS, "minimaps")
MONSTER = os.path.join(ASSETS, "monster")
NAMETAG = os.path.join(ASSETS, "nametag")
NUMBERS = os.path.join(ASSETS, "numbers")
MEDIA = os.path.join(ASSETS, "media")
MISC = os.path.join(ASSETS, "misc")
RUNE = os.path.join(ASSETS, "rune")
MAPS = os.path.join(ASSETS, "maps")


def asset(*parts: str) -> str:
    """Join path parts under assets/."""
    return os.path.join(ASSETS, *parts)


def minimap_dir(map_name: str) -> str:
    """Bundled/seed minimap assets: assets/minimaps/<map>/ (map.png etc.)."""
    return os.path.join(MINIMAPS, map_name)


def monster_dir(monster_name: str) -> str:
    return os.path.join(MONSTER, monster_name)


def get_app_root() -> Path:
    """Return the directory that should be the process cwd for relative paths."""
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # src/utils/paths.py -> project root is parents[2]
    return Path(__file__).resolve().parents[2]


def get_user_data_root() -> Path:
    """Writable user data root that survives dist/ rebuilds.

    Uses ``%USERPROFILE%\\.maplebot`` (same home as ``.maplebot_ui_state.json``).
    """
    return Path.home() / ".maplebot"


def user_maps_dir() -> Path:
    return get_user_data_root() / "maps"


def user_map_dir(map_name: str) -> Path:
    """Per-map user data: ~/.maplebot/maps/<map>/."""
    return user_maps_dir() / str(map_name)
