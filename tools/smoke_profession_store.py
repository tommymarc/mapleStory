# -*- coding: utf-8 -*-
"""Pre-build smoke: ProfessionConfigStore constructs; 剑客 must NOT be seeded."""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

def main():
    from src.ui.profession_config import ProfessionConfigStore

    assert hasattr(ProfessionConfigStore, "_ensure_builtin_profiles")
    assert not hasattr(ProfessionConfigStore, "_sword_profile"), (
        "_sword_profile must be removed"
    )
    assert callable(ProfessionConfigStore._ensure_builtin_profiles)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "config_professions.yaml")
        store = ProfessionConfigStore(path)
        names = store.names()
        assert "剑客" not in names, f"剑客 must not be seeded: {names}"
        assert store.selected_name() == "" or store.selected_name() in names

    for rel in ("config/config_professions.yaml", "dist/config/config_professions.yaml"):
        p = ROOT / rel
        if not p.exists():
            continue
        store = ProfessionConfigStore(str(p))
        assert "剑客" not in store.names(), f"剑客 still in {rel}: {store.names()}"
        text = p.read_text(encoding="utf-8")
        for expected in ("战士", "法师", "冰雷"):
            if expected + ":" in text or ("  " + expected) in text:
                assert expected in store.names(), f"{expected} missing in {rel}"

    print("smoke_profession_store OK")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("smoke_profession_store FAILED:", exc)
        raise
