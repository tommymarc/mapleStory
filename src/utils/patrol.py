"""Per-map smart_patrol bounds.

Writable copy lives under ~/.maplebot/maps/{map}/patrol.yaml (survives rebuilds).
assets/minimaps/{map}/patrol.yaml is an optional seed/default when user data
is missing. Engine merges these over config smart_patrol defaults at load_config.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml

from src.utils.paths import minimap_dir, user_map_dir


def assets_patrol_path(map_name: str) -> str:
    """Bundled/seed patrol.yaml under assets/minimaps/{map}/."""
    return os.path.join(minimap_dir(map_name), "patrol.yaml")


def user_patrol_path(map_name: str) -> str:
    """User-data patrol.yaml under ~/.maplebot/maps/{map}/."""
    return str(user_map_dir(map_name) / "patrol.yaml")


def patrol_path(map_name: str) -> str:
    """Preferred write path (always user data)."""
    return user_patrol_path(map_name)


def resolve_patrol_path(map_name: str) -> Optional[str]:
    """Path to load: user data if present, else assets seed, else None."""
    user = user_patrol_path(map_name)
    if os.path.isfile(user):
        return user
    assets = assets_patrol_path(map_name)
    if os.path.isfile(assets):
        return assets
    return None


def empty_patrol_doc(map_name: str) -> Dict[str, Any]:
    return {
        "map": map_name,
        "range": [0.25, 0.75],
        "preferred_y": None,
        "preferred_y_tol": 12.0,
        "rope_enable": False,
    }


def _as_range(raw: Any) -> List[float]:
    try:
        left, right = float(raw[0]), float(raw[1])
    except (TypeError, ValueError, IndexError):
        left, right = 0.25, 0.75
    left = max(0.0, min(1.0, left))
    right = max(0.0, min(1.0, right))
    if left > right:
        left, right = right, left
    return [left, right]


def load_patrol(map_name: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Load patrol.yaml; missing file yields defaults.

    When ``path`` is omitted, prefers ~/.maplebot user data over assets seed.
    """
    if path is None:
        path = resolve_patrol_path(map_name)
    doc = empty_patrol_doc(map_name)
    if not path or not os.path.isfile(path):
        return doc
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        return doc
    doc["map"] = str(raw.get("map") or map_name)
    if "range" in raw and raw["range"] is not None:
        doc["range"] = _as_range(raw["range"])
    if raw.get("preferred_y") is not None and str(raw.get("preferred_y")).strip() != "":
        try:
            doc["preferred_y"] = float(raw["preferred_y"])
        except (TypeError, ValueError):
            doc["preferred_y"] = None
    try:
        doc["preferred_y_tol"] = float(raw.get("preferred_y_tol", 12) or 12)
    except (TypeError, ValueError):
        doc["preferred_y_tol"] = 12.0
    if "rope_enable" in raw:
        val = raw["rope_enable"]
        if isinstance(val, str):
            doc["rope_enable"] = val.strip().lower() in ("1", "true", "yes", "on")
        else:
            doc["rope_enable"] = bool(val)
    return doc


def save_patrol(map_name: str, doc: Dict[str, Any], path: Optional[str] = None) -> str:
    """Write patrol.yaml to user data (or explicit path). Returns path."""
    path = path or user_patrol_path(map_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {
        "map": str(doc.get("map") or map_name),
        "range": _as_range(doc.get("range", [0.25, 0.75])),
        "preferred_y": doc.get("preferred_y", None),
        "preferred_y_tol": float(doc.get("preferred_y_tol", 12) or 12),
        "rope_enable": bool(doc.get("rope_enable", False)),
    }
    if out["preferred_y"] is not None:
        try:
            out["preferred_y"] = float(out["preferred_y"])
        except (TypeError, ValueError):
            out["preferred_y"] = None
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(out, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def merge_patrol_into_smart_patrol(
    smart_patrol_cfg: Optional[Dict[str, Any]],
    map_name: str,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a shallow-copied smart_patrol dict with per-map patrol.yaml overrides applied."""
    base = dict(smart_patrol_cfg or {})
    if path is None:
        file_path = resolve_patrol_path(map_name)
    else:
        file_path = path
    if not file_path or not os.path.isfile(file_path):
        return base
    patrol = load_patrol(map_name, path=file_path)
    base["range"] = list(patrol["range"])
    base["preferred_y_tol"] = float(patrol["preferred_y_tol"])
    base["rope_enable"] = bool(patrol["rope_enable"])
    if patrol.get("preferred_y") is not None:
        base["preferred_y"] = float(patrol["preferred_y"])
    return base
