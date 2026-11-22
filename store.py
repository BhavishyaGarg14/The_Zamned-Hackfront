import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from gemini_analyzer import get_commitments_from_gemini

log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent
CACHE_DIR = Path("/tmp") if os.getenv("VERCEL") else BASE_DIR
SAMPLE_FILE = BASE_DIR / "sample_data.json"

_lock = threading.RLock()
_state = {}
_listeners = []


def on_update(callback):
    _listeners.append(callback)


def _cache_path(username: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]", "_", username.lower())
    return CACHE_DIR / f"cache_{safe}.json"


def _set(username: str, data, source: str):
    _state[username] = {
        "data": data,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _try_gemini(username: str) -> bool:
    try:
        fresh = get_commitments_from_gemini(username)
    except Exception as exc:
        log.error("Gemini/Neo4j refresh failed for '%s': %s", username, exc)
        return False

    engine = getattr(get_commitments_from_gemini, "last_engine", "neo4j")
    _set(username, fresh, engine)
    try:
        _cache_path(username).write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

    for callback in _listeners:
        try:
            callback(fresh)
        except Exception:
            log.exception("on_update listener failed")
    return True


def get_commitments(username: str, refresh: bool = False):
    with _lock:
        if refresh:
            _try_gemini(username)
        if username not in _state:
            cp = _cache_path(username)
            if cp.exists():
                _set(username, json.loads(cp.read_text(encoding="utf-8")), "cache")
            elif not _try_gemini(username):
                _set(username, json.loads(SAMPLE_FILE.read_text(encoding="utf-8")), "sample")
        return _state[username]["data"]


def get_status(username: str):
    entry = _state.get(username) or {"source": None, "updated_at": None}
    return {"source": entry["source"], "updated_at": entry["updated_at"]}
