"""Short-term monster tracks with soft/ghost TTL for frame-drop resilience."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple


def _center(monster: Dict[str, Any]) -> Tuple[float, float]:
    x, y = monster["position"]
    w, h = monster["size"]
    return (x + w * 0.5, y + h * 0.5)


def _center_dist(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


class MonsterTracker:
    """Associate per-frame detections into stable tracks; keep soft boxes for TTL."""

    def __init__(self) -> None:
        self._next_id = 1
        self._tracks: Dict[int, Dict[str, Any]] = {}

    def clear(self) -> None:
        self._tracks.clear()

    def update(
        self,
        detections: List[Dict[str, Any]],
        now: Optional[float] = None,
        ttl_sec: float = 0.4,
        match_dist: float = 80.0,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Match live detections to existing tracks by center distance.

        Returns:
            (live_monsters_with_track_id, soft_ghost_monsters_within_ttl)

        Soft/ghost boxes are previous track poses that missed this frame but
        have not yet exceeded ttl_sec since last_seen.
        """
        now = time.time() if now is None else float(now)
        ttl_sec = max(0.0, float(ttl_sec))
        match_dist = max(1.0, float(match_dist))
        detections = list(detections or [])

        track_ids = list(self._tracks.keys())
        candidates = []
        for di, det in enumerate(detections):
            for tid in track_ids:
                dist = _center_dist(det, self._tracks[tid])
                if dist <= match_dist:
                    candidates.append((dist, di, tid))
        candidates.sort(key=lambda item: item[0])

        used_dets = set()
        matched_tracks = set()
        det_to_track = {}
        for _dist, di, tid in candidates:
            if di in used_dets or tid in matched_tracks:
                continue
            used_dets.add(di)
            matched_tracks.add(tid)
            det_to_track[di] = tid

        live_out: List[Dict[str, Any]] = []
        live_ids = set()
        for di, det in enumerate(detections):
            tid = det_to_track.get(di)
            if tid is None:
                tid = self._next_id
                self._next_id += 1
            self._tracks[tid] = {
                "id": tid,
                "name": det.get("name", "monster"),
                "position": tuple(det["position"]),
                "size": tuple(det["size"]),
                "score": det.get("score", 1.0),
                "last_seen": now,
            }
            live_ids.add(tid)
            out = dict(det)
            out["track_id"] = tid
            out["is_soft"] = False
            live_out.append(out)

        soft_out: List[Dict[str, Any]] = []
        expired = []
        for tid, track in list(self._tracks.items()):
            if tid in live_ids:
                continue
            age = now - float(track["last_seen"])
            if age > ttl_sec:
                expired.append(tid)
                continue
            soft_out.append({
                "name": track.get("name", "monster"),
                "position": tuple(track["position"]),
                "size": tuple(track["size"]),
                "score": track.get("score", 1.0),
                "track_id": tid,
                "is_soft": True,
            })

        for tid in expired:
            self._tracks.pop(tid, None)

        return live_out, soft_out