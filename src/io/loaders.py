# src/io/loaders.py
import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(path: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Load JSON from path. If file doesn't exist or is invalid, return default (or {}).
    """
    default = default or {}
    p = Path(path)
    if not p.exists():
        return default

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default