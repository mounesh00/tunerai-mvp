#!/usr/bin/env python3
"""Pre-deploy validation for TunerAI API."""
from __future__ import annotations
import compileall, importlib, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
sys.path.insert(0, str(API))
sys.path.insert(0, str(ROOT))
errors, ok = [], []

def check(label, fn):
    try:
        fn(); ok.append(label); print(f"[PASS] {label}")
    except Exception as e:
        errors.append(f"{label}: {e}"); print(f"[FAIL] {label}: {e}")

def structure():
    req = [
        API/"app"/"main.py", API/"app"/"models"/"user.py", API/"app"/"models"/"__init__.py",
        API/"app"/"api"/"__init__.py", API/"app"/"core"/"__init__.py", API/"app"/"db"/"__init__.py",
        ROOT/"ml"/"training"/"config.py", ROOT/"workers"/"celery_app.py",
        ROOT/"infra"/"docker"/"Dockerfile.api", ROOT/"infra"/"docker"/"Dockerfile.worker",
    ]
    miss = [str(p.relative_to(ROOT)) for p in req if not p.exists()]
    if miss: raise FileNotFoundError("Missing: " + ", ".join(miss))

def compile_py():
    for d in [API/"app", ROOT/"ml", ROOT/"workers"]:
        if not compileall.compile_dir(str(d), quiet=1):
            raise RuntimeError(f"compileall failed: {d}")

def import_models():
    m = importlib.import_module("app.models.user")
    assert hasattr(m, "User")

def import_main():
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    os.environ.setdefault("SECRET_KEY", "x"); os.environ.setdefault("JWT_SECRET_KEY", "y")
    m = importlib.import_module("app.main")
    assert hasattr(m, "app")

if __name__ == "__main__":
    print("TunerAI predeploy check")
    check("project structure", structure)
    check("python compileall", compile_py)
    check("import app.models.user", import_models)
    check("import app.main", import_main)
    print()
    if errors:
        print(f"FAILED ({len(errors)})"); [print(" -", e) for e in errors]; sys.exit(1)
    print(f"OK — {len(ok)} checks passed"); sys.exit(0)
