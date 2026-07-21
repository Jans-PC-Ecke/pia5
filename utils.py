# utils.py – Kern-Utilities mit Log-Rotation & JSON-Cache

import os
import json
import logging
import logging.handlers
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
os.makedirs(BASE_DIR, exist_ok=True)

# ─── LOGGING MIT ROTATION ───
log_file = BASE_DIR / "pia5.log"

root_logger = logging.getLogger('')
root_logger.setLevel(logging.INFO)

file_handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
root_logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
root_logger.addHandler(console_handler)

# ─── FARBEN ───
class Colors:
    RESET = '\033[0m'
    RED   = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE  = '\033[94m'
    CYAN  = '\033[96m'
    BOLD  = '\033[1m'

USE_COLOR = True

def cprint(color: str, text: str, file=None):
    if USE_COLOR:
        print(f"{color}{text}{Colors.RESET}", file=file)
    else:
        print(text, file=file)

# ─── JSON-CACHE ───
json_lock = threading.RLock()
_json_cache = {}
EMPTY_DICT = {}  # Konstante für Default

def lade_json(name: str, default=None, use_cache: bool = True):
    if default is None:
        default = EMPTY_DICT
    path = BASE_DIR / name
    with json_lock:
        if use_cache:
            cached = _json_cache.get(name)
            if cached and path.exists() and cached[0] == path.stat().st_mtime:
                return cached[1]
        if not path.exists():
            speichere_json(name, default)
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if use_cache:
                _json_cache[name] = (path.stat().st_mtime, data)
            return data
        except Exception as e:
            logging.error(f"lade_json Fehler bei {name}: {e}")
            return default

def speichere_json(name: str, daten, indent=2):
    path = BASE_DIR / name
    backup_path = path.with_suffix(path.suffix + ".bak")
    with json_lock:
        try:
            if path.exists():
                path.rename(backup_path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(daten, f, indent=indent, ensure_ascii=False)
            if backup_path.exists():
                backup_path.unlink()
            # Cache aktualisieren (vermeidet erneutes Lesen)
            _json_cache[name] = (path.stat().st_mtime, daten)
        except Exception as e:
            logging.error(f"speichere_json Fehler bei {name}: {e}", exc_info=True)
            if backup_path.exists():
                backup_path.rename(path)
            raise

# ─── KONFIG ───
KONFIG = lade_json("pia5_konfig.json", {
    "openweather_api_key": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
})

# ─── SPRACH-AUSGABE (gTTS) ───
def sprich(text: str):
    text = str(text).strip()
    if not text:
        return
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="de", slow=False)
        tmp_mp3 = BASE_DIR / "tmp_sprache.mp3"
        tts.save(tmp_mp3)
        subprocess.run(["mpg123", "-q", str(tmp_mp3)], check=False, timeout=15)
        tmp_mp3.unlink(missing_ok=True)
        return
    except Exception as e:
        logging.warning(f"gTTS-Fehler: {e}")
    print(f"[Pia] {text}")

def sprich_zu_datei(text: str) -> Path:
    text = str(text).strip()
    if not text:
        return None
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="de", slow=False)
        filename = BASE_DIR / f"tts_{uuid.uuid4().hex[:8]}.mp3"
        tts.save(str(filename))
        return filename
    except Exception as e:
        logging.error(f"gTTS-Datei Fehler: {e}")
        return None

# ─── TELEGRAM ───
def telegram_senden(nachricht: str, parse_mode: str = "MarkdownV2"):
    token = KONFIG.get("telegram_bot_token")
    chat_id = KONFIG.get("telegram_chat_id")
    if token and chat_id:
        try:
            import requests
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": nachricht, "parse_mode": parse_mode}
            requests.post(url, json=payload, timeout=5)
            return True
        except Exception as e:
            logging.error(f"Telegram-Fehler: {e}")
            return False
    return False

def send_notification(title: str, message: str, urgency: str = "normal"):
    try:
        subprocess.run(["notify-send", "-u", urgency, title, message], check=False)
    except:
        pass
    if KONFIG.get("telegram_bot_token") and KONFIG.get("telegram_chat_id"):
        telegram_senden(f"{title}\n{message}")

# ─── SYSTEM-BEFEHLE ───
def system_befehl(befehl, shell=True, check=False, timeout=None, capture_output=False):
    kwargs = {"shell": shell, "check": check, "timeout": timeout}
    if capture_output:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    try:
        result = subprocess.run(befehl, **kwargs)
        if capture_output:
            return result.stdout.strip() if result.returncode == 0 else ""
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Systembefehl fehlgeschlagen: {befehl} → {e}")
        return False

def is_process_running(process_name: str) -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-f", process_name], text=True).strip()
        return bool(out)
    except:
        return False

# ─── DATUMS-HELFER ───
DE_WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DE_MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]

def format_de_time(dt: datetime | None = None, fmt: str = "voll") -> str:
    if dt is None:
        dt = datetime.now()
    if fmt == "kurz":
        return dt.strftime("%H:%M")
    elif fmt == "datum":
        return f"{dt.day}. {DE_MONATE[dt.month-1]} {dt.year}"
    elif fmt == "wochentag":
        return DE_WOCHENTAGE[dt.weekday()]
    else:
        return f"{DE_WOCHENTAGE[dt.weekday()]}, {dt.day}. {DE_MONATE[dt.month-1]} {dt.year} – {dt.strftime('%H:%M')} Uhr"

# ─── ENV-OVERRIDES ───
def load_env_overrides():
    for key in list(KONFIG.keys()):
        env_key = f"PIA5_{key.upper()}"
        if val := os.getenv(env_key):
            KONFIG[key] = val
            logging.info(f"Konfig überschrieben via ENV: {env_key}")

load_env_overrides()

if __name__ == "__main__":
    print("utils.py geladen – mit Log-Rotation & JSON-Cache")