# assistant_core.py – Kern (kein LLM) – FINAL

import re
import logging
import hashlib
from datetime import datetime
import sys

from utils import sprich, send_notification, KONFIG, lade_json, speichere_json
from user_profiles import (
    get_active_username, login, logout, list_users,
    create_user, delete_user, switch_user, change_password, set_user_preference,
    get_active_user, get_user_by_name
)

# ─── PLUGIN-SYSTEM ───
from plugin_loader import load_plugins

_command_registry = {}

def register_command(trigger_words, func, description=""):
    if isinstance(trigger_words, str):
        trigger_words = [trigger_words]
    for word in trigger_words:
        _command_registry[word] = (func, description)

def get_command_handler(befehl):
    befehl_lower = befehl.lower()
    for word, (func, _) in _command_registry.items():
        if word in befehl_lower:
            return func
    return None

# ─── PIN-LOGIN ───
def _get_pin_user_map():
    users = lade_json("users.json", {"users": {}}, use_cache=False)
    pin_map = {}
    for username, data in users.get("users", {}).items():
        pin = data.get("pin")
        if pin:
            pin_map[pin] = username
    return pin_map

def authenticate_with_pin(pin: str) -> tuple[bool, str]:
    pin_map = _get_pin_user_map()
    if pin in pin_map:
        username = pin_map[pin]
        switch_user(username)
        return True, username
    return False, ""

def create_user_with_pin(username: str, pin: str, role: str = "user") -> str:
    users = lade_json("users.json", {"users": {}})
    if username in users["users"]:
        return f"❌ Benutzer {username} existiert bereits."
    users["users"][username] = {
        "pin": pin,
        "role": role,
        "sprache": "de",
        "antwort_stil": "freundlich",
        "created": datetime.now().isoformat()
    }
    speichere_json("users.json", users)
    return f"✅ Benutzer {username} mit PIN {pin} angelegt."

def change_user_pin(username: str, new_pin: str) -> str:
    users = lade_json("users.json", {"users": {}})
    if username not in users["users"]:
        return f"❌ Benutzer {username} nicht gefunden."
    users["users"][username]["pin"] = new_pin
    speichere_json("users.json", users)
    return f"✅ PIN für {username} auf {new_pin} geändert."

# ─── HILFEMENÜ ───
def zeige_hilfemenue() -> str:
    return """
Pia – dein persönlicher Assistent (RAG-basiert, ohne KI)

📌 **Alle Befehle:**

**👤 BENUTZER & AUTH**
  pin <1234> | login <user> <pin> | abmelden | wer bin ich
  benutzer anlegen <user> <pin> | benutzer löschen <user>
  benutzer listen | benutzer wechseln <user> | pin ändern <user> <pin>

**⏰ ZEIT & WETTER**
  uhrzeit | datum | wochentag | wetter | wetter morgen | wetter in Berlin

**📅 KALENDER**
  termin <Titel> <YYYY-MM-DD> <HH:MM> [Ort]
  erinnerung <Titel> <YYYY-MM-DD> <HH:MM>
  termin heute | termin alle | nächster termin
  termin löschen 5 | termin erledigen 5 | termin suche ...

**🔄 ROUTINEN**
  routine <Name> sprache <Trigger> | <Aktion1> | <Aktion2>
  routine <Name> zeit <HH:MM> | <Aktion1> | <Aktion2>
  routine alle | routine ausführen 5 | routine löschen 5
  routine bearbeiten 5 name Neu trigger zeit wert 14:00 aktionen licht an | wetter
  scheduler start | stopp

**🏠 SMART HOME (Tapo)**
  licht an | aus | helligkeit 50 | farbe rot
  ventilator an | aus | kaffeemaschine an | aus

**🛒 EINKAUFSLISTE**
  einkaufsliste | füge Milch hinzu | entferne Milch | erledigt Milch | leeren
  Einfaches Wort (z.B. "käse") → automatisch hinzufügen

**🧠 GEDÄCHTNIS (RAG)**
  merke: <Fakt> | was weißt du über mich? | suche <Begriff>
  erinnerst du dich an <Begriff>? | liste | vergiss Fakt 3
  was denkst du über <Thema>? → kombiniert deine Fakten

**📊 VERHALTENSANALYSE**
  analysiere | muster | verhalten | modus <frag_mich|mach_einfach|...>
  status | statistik

**💡 PROAKTIVE VORSCHLÄGE**
  vorschläge | proaktiv | analyse

**⏰ ALARM & TIMER**
  alarm um 06:30 | timer 5 Minuten
  erinnere mich in 10 Minuten an Müll | timer abbrechen

**📋 TÄGLICHE ÜBERSICHT**
  daily | heute | übersicht | was muss ich heute noch machen?

**❓ HILFE**
  hilfe | was kannst du | ?
"""

# ─── HAUPTFUNKTION ───
def befehl_verarbeiten(befehl: str) -> str:
    if not befehl:
        return ""

    clean = befehl.lower().strip()
    username = get_active_username()
    logging.info(f"[Pia] Befehl: '{befehl}'")

    # ─── KERNBEFEHLE ───
    if clean in ("hilfe", "help", "was kannst du", "befehle", "?"):
        antwort = zeige_hilfemenue()
        _save_conversation(username, "user", befehl)
        _save_conversation(username, "assistant", "Hilfe angezeigt")
        return antwort

    # PIN-Login & Benutzerverwaltung
    if "pin" in clean:
        match = re.search(r'pin\s+(\d+)', clean)
        if match:
            success, username = authenticate_with_pin(match.group(1))
            if success:
                antwort = f"Angemeldet als {username}"
                sprich(f"Hallo {username}!")
                return antwort
            return "❌ Falsche PIN"
        return "Bitte gib deine PIN ein: 'pin 1234'"

    if "abmelden" in clean or "logout" in clean:
        antwort = logout()
        sprich(antwort)
        return antwort

    if "wer bin ich" in clean:
        user = get_active_user()
        return f"Du bist {user.get('name', 'Unbekannt')} (Rolle: {user.get('role', 'user')})"

    if "benutzer anlegen" in clean:
        match = re.search(r'benutzer anlegen\s+(\w+)\s+(\d+)', clean)
        if match:
            return create_user_with_pin(match.group(1), match.group(2))
        return "Format: 'benutzer anlegen julia 5678'"

    if "benutzer löschen" in clean:
        match = re.search(r'benutzer löschen\s+(\w+)', clean)
        if match:
            return delete_user(match.group(1))
        return "Format: 'benutzer löschen julia'"

    if "benutzer listen" in clean:
        return list_users()

    if "benutzer wechseln" in clean:
        match = re.search(r'benutzer wechseln\s+(\w+)', clean)
        if match:
            return switch_user(match.group(1))
        return "Format: 'benutzer wechseln julia'"

    if "pin ändern" in clean:
        match = re.search(r'pin ändern\s+(\w+)\s+(\d+)', clean)
        if match:
            return change_user_pin(match.group(1), match.group(2))
        return "Format: 'pin ändern julia 9876'"

    # ─── PLUGIN-BEFEHLE ───
    handler = get_command_handler(befehl)
    if handler:
        try:
            antwort = handler(befehl)
            _save_conversation(username, "user", befehl)
            _save_conversation(username, "assistant", antwort[:200] + "..." if len(antwort) > 200 else antwort)
            return antwort
        except Exception as e:
            logging.error(f"Plugin-Fehler: {e}")
            return f"Plugin-Fehler: {e}"

    # ─── INTENT-ERKENNUNG ───
    try:
        from plugins.intent_plugin import recognize_intent
        intent_name, action = recognize_intent(befehl)
        if intent_name and action:
            if isinstance(action, str):
                if intent_name == "einkaufsliste_direkt":
                    antwort = action
                elif intent_name in ["wetter", "uhrzeit", "einkaufsliste", "daily"]:
                    antwort = befehl_verarbeiten(action)
                else:
                    antwort = befehl_verarbeiten(action)
            else:
                antwort = str(action)
            _save_conversation(username, "user", befehl)
            _save_conversation(username, "assistant", antwort[:200] + "..." if len(antwort) > 200 else antwort)
            return antwort
    except Exception as e:
        logging.error(f"Intent-Fehler: {e}")

    # ─── FALLBACK ───
    antwort = "Befehl nicht erkannt. Tippe 'hilfe' für eine Übersicht."
    _save_conversation(username, "user", befehl)
    _save_conversation(username, "assistant", antwort)
    return antwort

# ─── KONTEXT-HELFER ───
def _save_conversation(username, role, content):
    try:
        from plugins.memory_plugin import add_to_conversation
        if content and len(content) < 500:
            add_to_conversation(role, content, username)
    except Exception as e:
        pass

# ─── PLUGINS LADEN ───
load_plugins(sys.modules[__name__])

# ─── TOOLS EXPORT ───
def tools_holen():
    return [
        ("befehl_verarbeiten", befehl_verarbeiten, "Kern"),
        ("create_user_with_pin", create_user_with_pin, "Benutzer mit PIN"),
        ("change_user_pin", change_user_pin, "PIN ändern"),
    ]