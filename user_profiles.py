# user_profiles.py – Komplette Benutzerverwaltung mit Cache

import os
import json
import hashlib
import secrets
import re
import time
from datetime import datetime
from pathlib import Path
from utils import lade_json, speichere_json, logging, sprich, BASE_DIR

PROFILE_FILE = "users.json"
SESSION_FILE = "active_user.json"

DEFAULT_USERS = {
    "jan": {
        "name": "Jan",
        "password_hash": hashlib.sha256("standard".encode()).hexdigest(),
        "role": "admin",
        "sprache": "de",
        "antwort_stil": "frech_direkt",
        "lieblingsfarbe": "orange",
        "lieblingsmusik": "metal",
        "wohnort": "Eschwege",
        "weckzeit": "06:30",
        "bettszeit": "22:00",
        "created": datetime.now().isoformat(),
        "last_login": None
    }
}

# ─── CACHE FÜR get_active_user() ───
_active_user_cache = {"username": None, "timestamp": None}
CACHE_TTL = 5  # Sekunden

def _get_users():
    return lade_json(PROFILE_FILE, {"users": DEFAULT_USERS.copy()})

def _save_users(data):
    speichere_json(PROFILE_FILE, data)

def _get_active():
    global _active_user_cache
    now = time.time()
    if (_active_user_cache["username"] is not None and 
        _active_user_cache["timestamp"] is not None and
        now - _active_user_cache["timestamp"] < CACHE_TTL):
        return {"username": _active_user_cache["username"]}
    data = lade_json(SESSION_FILE, {"username": "jan", "last_active": None})
    _active_user_cache["username"] = data.get("username", "jan")
    _active_user_cache["timestamp"] = now
    return data

def _save_active(data):
    global _active_user_cache
    _active_user_cache["username"] = data.get("username", "jan")
    _active_user_cache["timestamp"] = time.time()
    speichere_json(SESSION_FILE, data)

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _generate_token() -> str:
    return secrets.token_hex(32)

def _create_user_files(username: str):
    user_files = {
        f"routinen_{username}.json": {"routinen": []},
        f"shopping_{username}.json": {"items": []},
        f"kalender_{username}.json": {"termine": []},
        f"memory_{username}.json": {"facts": [], "conversations": [], "preferences": {}},
        f"notizen_{username}.json": {"notizen": []},
    }
    for filename, default_content in user_files.items():
        filepath = BASE_DIR / filename
        if not filepath.exists():
            speichere_json(filename, default_content)
            logging.info(f"📄 {filename} für Benutzer {username} erstellt.")
    return True

# ─── BENUTZERVERWALTUNG ───

def create_user(username: str, password: str, role: str = "user") -> str:
    username = username.lower().strip()
    if not re.match(r'^[a-z0-9_]{2,20}$', username):
        return "❌ Benutzername muss 2-20 Zeichen lang sein und nur Kleinbuchstaben, Zahlen und Unterstriche enthalten."
    data = _get_users()
    if username in data["users"]:
        return f"❌ Benutzer '{username}' existiert bereits."
    if len(password) < 4:
        return "❌ Passwort muss mindestens 4 Zeichen lang sein."
    data["users"][username] = {
        "name": username,
        "password_hash": _hash_password(password),
        "role": role,
        "sprache": "de",
        "antwort_stil": "freundlich",
        "created": datetime.now().isoformat(),
        "last_login": None
    }
    _save_users(data)
    _create_user_files(username)
    return f"✅ Benutzer '{username}' wurde erstellt (Rolle: {role})."

def delete_user(username: str, admin_user: str = "jan") -> str:
    username = username.lower().strip()
    if username == admin_user:
        return "❌ Du kannst den Admin-Benutzer nicht löschen."
    data = _get_users()
    if username not in data["users"]:
        return f"❌ Benutzer '{username}' nicht gefunden."
    del data["users"][username]
    _save_users(data)
    for pattern in [f"routinen_{username}.json", f"shopping_{username}.json", 
                    f"kalender_{username}.json", f"memory_{username}.json",
                    f"notizen_{username}.json"]:
        filepath = BASE_DIR / pattern
        if filepath.exists():
            filepath.unlink()
            logging.info(f"🗑️ {pattern} gelöscht.")
    active = _get_active()
    if active.get("username") == username:
        _save_active({"username": "jan", "last_active": datetime.now().isoformat()})
    return f"✅ Benutzer '{username}' gelöscht."

def login(username: str, password: str) -> bool:
    username = username.lower().strip()
    data = _get_users()
    if username not in data["users"]:
        return False
    user = data["users"][username]
    if user["password_hash"] == _hash_password(password):
        _save_active({
            "username": username,
            "last_active": datetime.now().isoformat(),
            "token": _generate_token()
        })
        user["last_login"] = datetime.now().isoformat()
        _save_users(data)
        return True
    return False

def logout() -> str:
    _save_active({"username": "jan", "last_active": datetime.now().isoformat()})
    return "✅ Abgemeldet. Zurück zu Jan."

def get_active_user() -> dict:
    active = _get_active()
    username = active.get("username", "jan")
    data = _get_users()
    if username not in data["users"]:
        if "jan" not in data["users"]:
            data["users"]["jan"] = DEFAULT_USERS["jan"]
            _save_users(data)
            _create_user_files("jan")
        _save_active({"username": "jan", "last_active": datetime.now().isoformat()})
        return data["users"]["jan"]
    return data["users"][username]

def get_active_username() -> str:
    active = _get_active()
    return active.get("username", "jan")

def get_user_by_name(username: str) -> dict | None:
    data = _get_users()
    return data["users"].get(username.lower())

def list_users() -> str:
    data = _get_users()
    users = data["users"]
    if not users:
        return "👥 Keine Benutzer gefunden."
    ausgabe = "👥 Benutzer:\n"
    for name, user in users.items():
        role = user.get('role', 'user')
        last_login = user.get('last_login', 'Nie')
        if last_login:
            last_login = last_login[:10]
        ausgabe += f"  • {name} ({role}) – zuletzt: {last_login}\n"
    return ausgabe.strip()

def switch_user(username: str) -> str:
    username = username.lower().strip()
    data = _get_users()
    if username not in data["users"]:
        return f"❌ Benutzer '{username}' nicht gefunden."
    _save_active({
        "username": username,
        "last_active": datetime.now().isoformat(),
        "token": _generate_token()
    })
    return f"✅ Zu Benutzer '{username}' gewechselt."

def change_password(username: str, old_password: str, new_password: str) -> str:
    username = username.lower().strip()
    if len(new_password) < 4:
        return "❌ Neues Passwort muss mindestens 4 Zeichen lang sein."
    data = _get_users()
    if username not in data["users"]:
        return f"❌ Benutzer '{username}' nicht gefunden."
    user = data["users"][username]
    if user["password_hash"] != _hash_password(old_password):
        return "❌ Altes Passwort ist falsch."
    user["password_hash"] = _hash_password(new_password)
    _save_users(data)
    return f"✅ Passwort für '{username}' geändert."

# ─── PRÄFERENZEN ───

def set_user_preference(username: str, key: str, value: str) -> str:
    username = username.lower().strip()
    data = _get_users()
    if username not in data["users"]:
        return f"❌ Benutzer '{username}' nicht gefunden."
    data["users"][username][key] = value
    _save_users(data)
    return f"✅ Präferenz '{key}' auf '{value}' gesetzt."

def get_user_preference(username: str, key: str, default=None):
    user = get_user_by_name(username)
    if not user:
        return default
    return user.get(key, default)

def get_antwort_stil() -> str:
    user = get_active_user()
    return user.get("antwort_stil", "frech_direkt")

def get_user_file(username: str, file_type: str) -> str:
    return f"{file_type}_{username}.json"

def get_user_info() -> dict:
    user = get_active_user()
    return {
        "name": user.get("name", "Jan"),
        "wohnort": user.get("wohnort", ""),
        "antwort_stil": user.get("antwort_stil", "frech_direkt"),
        "lieblingsfarbe": user.get("lieblingsfarbe", ""),
        "lieblingsmusik": user.get("lieblingsmusik", "")
    }

# ─── TOOLS EXPORT ───

def tools_holen():
    return [
        ("create_user", create_user, "Benutzer"),
        ("delete_user", delete_user, "Benutzer"),
        ("login", login, "Benutzer"),
        ("logout", logout, "Benutzer"),
        ("list_users", list_users, "Benutzer"),
        ("switch_user", switch_user, "Benutzer"),
        ("change_password", change_password, "Benutzer"),
        ("set_user_preference", set_user_preference, "Benutzer"),
        ("get_active_user", get_active_user, "Benutzer"),
        ("get_active_username", get_active_username, "Benutzer"),
        ("get_user_info", get_user_info, "Benutzer"),
    ]