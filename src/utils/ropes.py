"""Rope edge storage and helpers for smart_patrol layer changes (P2).

Writable copy: ~/.maplebot/maps/{map}/ropes.yaml (survives dist rebuilds).
assets/minimaps/{map}/ropes.yaml is an optional seed when user data is missing.

Coordinates for start/end are live minimap inset pixels — the same space as
``get_player_location_on_minimap`` / smart_patrol Return (not map.png global
unless map.png size equals the live inset content size).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from src.utils.paths import minimap_dir, user_map_dir

Point = Tuple[float, float]
TZ_SHANGHAI = timezone(timedelta(hours=8))


def assets_ropes_path(map_name: str) -> str:
    """Bundled/seed ropes.yaml under assets/minimaps/{map}/."""
    return os.path.join(minimap_dir(map_name), "ropes.yaml")


def user_ropes_path(map_name: str) -> str:
    """User-data ropes.yaml under ~/.maplebot/maps/{map}/."""
    return str(user_map_dir(map_name) / "ropes.yaml")


def ropes_path(map_name: str) -> str:
    """Preferred write path (always user data)."""
    return user_ropes_path(map_name)


def resolve_ropes_path(map_name: str) -> Optional[str]:
    """Path to load: user data if present, else assets seed, else None."""
    user = user_ropes_path(map_name)
    if os.path.isfile(user):
        return user
    assets = assets_ropes_path(map_name)
    if os.path.isfile(assets):
        return assets
    return None


def _as_point(raw: Any) -> Optional[Point]:
    try:
        x, y = float(raw[0]), float(raw[1])
    except (TypeError, ValueError, IndexError):
        return None
    return (x, y)


def normalize_edge(raw: Any, index: int = 0) -> Optional[Dict[str, Any]]:
    """Normalize one edge dict; return None if invalid."""
    if not isinstance(raw, dict):
        return None
    start = _as_point(raw.get("start"))
    end = _as_point(raw.get("end"))
    if start is None or end is None:
        return None
    direction = str(raw.get("direction") or "").strip().lower()
    if direction not in ("up", "down"):
        # Infer from vertical delta on minimap (smaller y = higher on screen).
        direction = "up" if end[1] < start[1] else "down"
    edge_id = str(raw.get("id") or f"rope_{index + 1}")
    edge: Dict[str, Any] = {
        "id": edge_id,
        "start": [float(start[0]), float(start[1])],
        "end": [float(end[0]), float(end[1])],
        "direction": direction,
    }
    hint = raw.get("duration_hint_sec")
    if hint is not None:
        try:
            edge["duration_hint_sec"] = float(hint)
        except (TypeError, ValueError):
            pass
    if raw.get("recorded_at"):
        edge["recorded_at"] = str(raw["recorded_at"])
    return edge


def empty_rope_doc(map_name: str) -> Dict[str, Any]:
    return {
        "map": map_name,
        "preferred_y": None,
        "preferred_y_tol": 12,
        "edges": [],
    }


def load_ropes(map_name: str, path: Optional[str] = None) -> Dict[str, Any]:
    """Load ropes.yaml for a map; missing file yields an empty doc.

    When ``path`` is omitted, prefers ~/.maplebot user data over assets seed.
    """
    if path is None:
        path = resolve_ropes_path(map_name)
    doc = empty_rope_doc(map_name)
    if not path or not os.path.isfile(path):
        return doc
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        return doc
    doc["map"] = str(raw.get("map") or map_name)
    if raw.get("preferred_y") is not None:
        try:
            doc["preferred_y"] = float(raw["preferred_y"])
        except (TypeError, ValueError):
            doc["preferred_y"] = None
    try:
        doc["preferred_y_tol"] = float(raw.get("preferred_y_tol", 12))
    except (TypeError, ValueError):
        doc["preferred_y_tol"] = 12.0
    edges: List[Dict[str, Any]] = []
    for i, item in enumerate(raw.get("edges") or []):
        edge = normalize_edge(item, i)
        if edge is not None:
            edges.append(edge)
    doc["edges"] = edges
    return doc


def save_ropes(map_name: str, doc: Dict[str, Any], path: Optional[str] = None) -> str:
    """Write ropes.yaml to user data (or explicit path). Returns path."""
    path = path or user_ropes_path(map_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = {
        "map": str(doc.get("map") or map_name),
        "preferred_y": doc.get("preferred_y", None),
        "preferred_y_tol": float(doc.get("preferred_y_tol", 12) or 12),
        "edges": [],
    }
    for i, item in enumerate(doc.get("edges") or []):
        edge = normalize_edge(item, i)
        if edge is not None:
            # YAML-friendly lists
            edge["start"] = [float(edge["start"][0]), float(edge["start"][1])]
            edge["end"] = [float(edge["end"][0]), float(edge["end"][1])]
            out["edges"].append(edge)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(out, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def append_edge(
    map_name: str,
    start: Sequence[float],
    end: Sequence[float],
    direction: Optional[str] = None,
    duration_hint_sec: Optional[float] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Append one recorded climb edge and persist to user data. Returns the new edge."""
    # Load from resolve (user|assets) when path omitted; always save to user path.
    doc = load_ropes(map_name, path=path)
    idx = len(doc["edges"])
    raw = {
        "id": f"rope_{idx + 1}",
        "start": [float(start[0]), float(start[1])],
        "end": [float(end[0]), float(end[1])],
        "direction": direction,
        "recorded_at": datetime.now(TZ_SHANGHAI).isoformat(timespec="seconds"),
    }
    if duration_hint_sec is not None:
        raw["duration_hint_sec"] = float(duration_hint_sec)
    edge = normalize_edge(raw, idx)
    if edge is None:
        raise ValueError("Invalid rope edge coordinates")
    doc["edges"].append(edge)
    # Seed preferred_y from first successful climb end if unset.
    if doc.get("preferred_y") is None:
        doc["preferred_y"] = float(edge["end"][1])
    save_path = path if path is not None else user_ropes_path(map_name)
    save_ropes(map_name, doc, path=save_path)
    return edge


def dist2(a: Sequence[float], b: Sequence[float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return dx * dx + dy * dy


def nearest_edge(
    edges: Sequence[Dict[str, Any]],
    player_xy: Sequence[float],
    *,
    prefer_end_y: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Pick nearest rope start; optionally bias toward edges whose end is near prefer_end_y."""
    if not edges:
        return None
    best = None
    best_score = None
    for edge in edges:
        start = edge.get("start")
        if start is None:
            continue
        score = dist2(player_xy, start)
        if prefer_end_y is not None:
            end = edge.get("end")
            if end is not None:
                # Prefer edges that land closer to the preferred band.
                score = score + 0.35 * ((float(end[1]) - float(prefer_end_y)) ** 2)
        if best_score is None or score < best_score:
            best_score = score
            best = edge
    return best


def is_off_preferred_band(
    player_y: Optional[float],
    preferred_y: Optional[float],
    tol: float,
) -> bool:
    if player_y is None or preferred_y is None:
        return False
    try:
        return abs(float(player_y) - float(preferred_y)) > float(tol)
    except (TypeError, ValueError):
        return False


def delete_edge(
    map_name: str,
    edge_id: str,
    path: Optional[str] = None,
) -> bool:
    """Remove one edge by id and persist. Returns True if an edge was removed."""
    doc = load_ropes(map_name, path=path)
    before = len(doc.get("edges") or [])
    doc["edges"] = [e for e in (doc.get("edges") or []) if str(e.get("id")) != str(edge_id)]
    if len(doc["edges"]) == before:
        return False
    save_path = path if path is not None else user_ropes_path(map_name)
    save_ropes(map_name, doc, path=save_path)
    return True
