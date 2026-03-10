from __future__ import annotations

import importlib.util
from pathlib import Path

_APP_FILE = Path(__file__).resolve().with_name("app.py")
_spec = importlib.util.spec_from_file_location("rosman_app", _APP_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load Flask app module at {_APP_FILE}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

app = _module.app