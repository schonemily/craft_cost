import os
import json
import tempfile
from typing import Optional, Dict, Any

DB_PATH = os.environ.get("LOCAL_DB_PATH", "/data/users.json")


def _ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _load() -> Dict[str, Any]:
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"seq": 1, "users": []}


def _save(data: Dict[str, Any]) -> None:
    _ensure_parent_dir(DB_PATH)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="users_", suffix=".json", dir=os.path.dirname(DB_PATH) or None)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, DB_PATH)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def get_by_email(email: str) -> Optional[Dict[str, Any]]:
    email = (email or "").strip().lower()
    data = _load()
    for u in data.get("users", []):
        if (u.get("email") or "").lower() == email:
            return u
    return None


def get_by_id(uid: int) -> Optional[Dict[str, Any]]:
    data = _load()
    for u in data.get("users", []):
        if int(u.get("id") or 0) == int(uid):
            return u
    return None


def add_user(email: str, password_hash: str, role: str = "user") -> Dict[str, Any]:
    data = _load()
    # prevent duplicates
    if get_by_email(email):
        raise ValueError("email_taken")
    uid = int(data.get("seq", 1))
    user = {"id": uid, "email": email.strip().lower(), "password_hash": password_hash, "role": role}
    data.setdefault("users", []).append(user)
    data["seq"] = uid + 1
    _save(data)
    return user
