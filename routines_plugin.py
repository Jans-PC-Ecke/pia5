# plugins/routines_plugin.py – Routinen (mit fixer Bearbeitung)

import json
import threading
import time
import re
import importlib
from datetime import datetime
from pathlib import Path
from utils import lade_json, speichere_json, send_notification
import logging

# ─── KOMPILIERTE REGEX ───
_RE_ID = re.compile(r'(?:löschen|loeschen)\s+(\d+)')
_RE_DEAKTIVIEREN = re.compile(r'(?:deaktivieren|aus)\s+(\d+)')
_RE_AKTIVIEREN = re.compile(r'(?:aktivieren|an)\s+(\d+)')
_RE_AUSFUEHREN = re.compile(r'(?:ausführen|start)\s+(\d+)')
_RE_BEARBEITEN = re.compile(r'(?:bearbeiten|edit|änder|update)\s+(\d+)')
_RE_WOCHENTAGE = re.compile(r'wochentage\s+([\w\s,]+)')
_RE_ZEIT = re.compile(r'\d{1,2}:\d{2}')
_RE_ROUTINE_SPLIT = re.compile(r'\s*\|\s*')
_RE_NAME = re.compile(r'name\s+([^\|]+)')
_RE_TRIGGER = re.compile(r'trigger\s+(zeit|sprache)')
_RE_WERT = re.compile(r'wert\s+([^\|]+)')
_RE_AKTIONEN = re.compile(r'aktionen\s+([^\|]+)')

# ─── importlib-CACHE ───
_assistant_module = None

def _get_assistant():
    global _assistant_module
    if _assistant_module is None:
        _assistant_module = importlib.import_module('assistant_core')
    return _assistant_module

# ─── STATUS-DATEI ───
STATUS_FILE = Path("scheduler_status.json")

def _write_status(running):
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump({"running": running, "updated": datetime.now().isoformat()}, f)
    except:
        pass

def _read_status():
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                data = json.load(f)
                return data.get("running", False)
        except:
            pass
    return False

def register(core):
    core.register_command(["routine", "scheduler"], handle_routines, "Routinen & Scheduler verwalten")

def _get_current_user():
    try:
        active_file = Path("active_user.json")
        if active_file.exists():
            with open(active_file, "r") as f:
                data = json.load(f)
            return data.get("username", "jan")
    except:
        pass
    return "jan"

def _get_user_file(username=None):
    if username is None:
        username = _get_current_user()
    return f"routinen_{username}.json"

def _lade_routinen(username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"routinen": []})
    if not isinstance(daten, dict) or "routinen" not in daten:
        logging.warning(f"[Routinen] Ungültiges Format in {file} – setze Standard")
        daten = {"routinen": []}
        speichere_json(file, daten)
    return daten

def _speichere_routinen(daten, username=None):
    file = _get_user_file(username)
    speichere_json(file, daten)

def _naechste_id(username=None):
    daten = _lade_routinen(username)
    max_id = max([r.get("id", 0) for r in daten["routinen"]], default=0)
    return max_id + 1

def _validate_time(time_str):
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            return False
        h, m = int(parts[0]), int(parts[1])
        return 0 <= h <= 23 and 0 <= m <= 59
    except:
        return False

def routine_hinzufuegen(name, trigger, trigger_wert, aktionen, wochentage=None, username=None):
    if trigger == "zeit" and not _validate_time(trigger_wert):
        return "❌ Ungültige Uhrzeit. Format: HH:MM (z.B. 14:30)"
    
    daten = _lade_routinen(username)
    neue_routine = {
        "id": _naechste_id(username),
        "name": name.strip(),
        "trigger": trigger,
        "trigger_text": trigger_wert if trigger == "sprache" else "",
        "trigger_zeit": trigger_wert if trigger == "zeit" else "",
        "trigger_wochentage": wochentage or [],
        "aktionen": aktionen,
        "aktiv": True,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    daten["routinen"].append(neue_routine)
    _speichere_routinen(daten, username)
    msg = f"Routine '{name}' hinzugefügt ({len(aktionen)} Aktionen)"
    send_notification("Neue Routine", msg)
    return msg

def routine_loeschen(routine_id, username=None):
    daten = _lade_routinen(username)
    for i, r in enumerate(daten["routinen"]):
        if r.get("id") == routine_id:
            name = r.get("name", "?")
            del daten["routinen"][i]
            _speichere_routinen(daten, username)
            return f"Routine '{name}' gelöscht."
    return f"Routine mit ID {routine_id} nicht gefunden."

def routine_toggle(routine_id, username=None):
    daten = _lade_routinen(username)
    for r in daten["routinen"]:
        if r.get("id") == routine_id:
            r["aktiv"] = not r.get("aktiv", True)
            _speichere_routinen(daten, username)
            status = "aktiviert" if r["aktiv"] else "deaktiviert"
            return f"Routine '{r.get('name', '?')}' {status}."
    return f"Routine mit ID {routine_id} nicht gefunden."

def routine_aktualisieren(routine_id, name, trigger, trigger_wert, aktionen, wochentage=None, username=None):
    if trigger == "zeit" and not _validate_time(trigger_wert):
        return "❌ Ungültige Uhrzeit. Format: HH:MM (z.B. 14:30)"
    
    daten = _lade_routinen(username)
    for r in daten["routinen"]:
        if r.get("id") == routine_id:
            r["name"] = name.strip()
            r["trigger"] = trigger
            if trigger == "sprache":
                r["trigger_text"] = trigger_wert
                r["trigger_zeit"] = ""
            else:
                r["trigger_zeit"] = trigger_wert
                r["trigger_text"] = ""
            r["trigger_wochentage"] = wochentage or []
            r["aktionen"] = aktionen
            _speichere_routinen(daten, username)
            return f"Routine '{name}' aktualisiert."
    return f"Routine mit ID {routine_id} nicht gefunden."

def routinen_alle(username=None):
    daten = _lade_routinen(username)
    if not daten["routinen"]:
        return "Keine Routinen vorhanden."
    ausgabe = "Routinen:\n"
    for r in daten["routinen"]:
        status = "✓" if r.get("aktiv", True) else "✗"
        ausgabe += f"  {status} ID {r['id']}: {r['name']} ({r['trigger']}"
        if r['trigger'] == "zeit":
            ausgabe += f" um {r.get('trigger_zeit', '?')}"
        elif r['trigger'] == "sprache":
            ausgabe += f" bei '{r.get('trigger_text', '?')}'"
        ausgabe += f") – {len(r.get('aktionen', []))} Aktionen\n"
    return ausgabe.strip()

def routine_ausfuehren(routine_id, username=None):
    daten = _lade_routinen(username)
    for r in daten["routinen"]:
        if r.get("id") == routine_id:
            if not r.get("aktiv", True):
                return f"Routine '{r.get('name', '?')}' ist deaktiviert."
            assistant = _get_assistant()
            befehl_verarbeiten = assistant.befehl_verarbeiten
            ergebnisse = []
            for aktion in r.get("aktionen", []):
                try:
                    antwort = befehl_verarbeiten(aktion)
                    ergebnisse.append(antwort)
                except Exception as e:
                    ergebnisse.append(f"Fehler: {e}")
            gesamt_antwort = "\n".join(ergebnisse)
            send_notification("Routine ausgeführt", f"{r['name']}: {len(ergebnisse)} Aktionen")
            return gesamt_antwort
    return f"Routine mit ID {routine_id} nicht gefunden."

_scheduler_running = False
_scheduler_thread = None

def _scheduler_loop():
    global _scheduler_running
    from user_profiles import switch_user, get_active_username
    logging.info("[Scheduler] Loop gestartet (optimiert – nur aktiver User)")
    while _scheduler_running:
        try:
            jetzt = datetime.now()
            aktuell = jetzt.strftime("%H:%M")
            wochentag = jetzt.strftime("%a").lower()[:2]
            username = get_active_username()
            daten = _lade_routinen(username)
            if not isinstance(daten, dict) or "routinen" not in daten:
                time.sleep(30)
                continue
            for r in daten.get("routinen", []):
                if not r.get("aktiv", True):
                    continue
                if r.get("trigger") != "zeit":
                    continue
                trigger_zeit = r.get("trigger_zeit", "")
                if trigger_zeit != aktuell:
                    continue
                wochentage = r.get("trigger_wochentage", [])
                if wochentage and wochentag not in wochentage:
                    continue
                logging.info(f"[Scheduler] Führe Routine '{r['name']}' für {username} aus (Zeit: {aktuell})")
                try:
                    assistant = _get_assistant()
                    befehl_verarbeiten = assistant.befehl_verarbeiten
                    switch_user(username)
                    for aktion in r.get("aktionen", []):
                        befehl_verarbeiten(aktion)
                    send_notification("Routine ausgeführt", f"{r['name']} (Zeit: {aktuell})")
                except Exception as e:
                    logging.error(f"[Scheduler] Fehler bei Routine {r['name']}: {e}")
            time.sleep(30)
        except Exception as e:
            logging.error(f"[Scheduler] Loop Fehler: {e}")
            time.sleep(60)
    logging.info("[Scheduler] Loop beendet")
    _write_status(False)

def starte_scheduler():
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return "Scheduler läuft bereits."
    logging.info("[Scheduler] Starte Scheduler...")
    _scheduler_running = True
    _write_status(True)
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logging.info("[Scheduler] Scheduler gestartet (optimiert)")
    return "Routine-Scheduler gestartet."

def stoppe_scheduler():
    global _scheduler_running
    if not _scheduler_running:
        return "Scheduler läuft nicht."
    _scheduler_running = False
    _write_status(False)
    logging.info("[Scheduler] Scheduler gestoppt")
    return "Routine-Scheduler gestoppt."

def handle_routines(befehl):
    """Verarbeitet alle Routinen-Befehle – mit fixer Bearbeitung."""
    clean = befehl.lower().strip()
    username = _get_current_user()

    # ─── ALLE ───
    if "alle" in clean:
        return routinen_alle(username)
    
    # ─── LÖSCHEN ───
    match = _RE_ID.search(clean)
    if match:
        return routine_loeschen(int(match.group(1)), username)
    
    # ─── DEAKTIVIEREN ───
    match = _RE_DEAKTIVIEREN.search(clean)
    if match:
        return routine_toggle(int(match.group(1)), username)
    
    # ─── AKTIVIEREN ───
    match = _RE_AKTIVIEREN.search(clean)
    if match:
        return routine_toggle(int(match.group(1)), username)
    
    # ─── AUSFÜHREN ───
    match = _RE_AUSFUEHREN.search(clean)
    if match:
        return routine_ausfuehren(int(match.group(1)), username)
    
    # ─── BEARBEITEN (FIX) ───
    if "bearbeiten" in clean or "edit" in clean:
        match = _RE_BEARBEITEN.search(clean)
        if not match:
            return "Format: 'routine bearbeiten 5 name Neu trigger zeit wert 14:00 aktionen licht an | wetter'"
        
        routine_id = int(match.group(1))
        
        # Extrahiere Felder mit flexiblerer Suche
        name_match = _RE_NAME.search(clean)
        trigger_match = _RE_TRIGGER.search(clean)
        wert_match = _RE_WERT.search(clean)
        aktionen_match = _RE_AKTIONEN.search(clean)
        
        # Wenn nichts gefunden wurde, zeige Hilfe
        if not name_match and not trigger_match and not wert_match and not aktionen_match:
            return "Format: 'routine bearbeiten 5 name Neu trigger zeit wert 14:00 aktionen licht an | wetter'"
        
        daten = _lade_routinen(username)
        for r in daten["routinen"]:
            if r.get("id") == routine_id:
                if name_match:
                    r["name"] = name_match.group(1).strip()
                if trigger_match:
                    r["trigger"] = trigger_match.group(1).strip()
                if wert_match:
                    wert = wert_match.group(1).strip()
                    if r["trigger"] == "zeit":
                        if not _validate_time(wert):
                            return "❌ Ungültige Uhrzeit. Format: HH:MM"
                        r["trigger_zeit"] = wert
                        r["trigger_text"] = ""
                    else:
                        r["trigger_text"] = wert
                        r["trigger_zeit"] = ""
                if aktionen_match:
                    r["aktionen"] = [a.strip() for a in aktionen_match.group(1).split("|") if a.strip()]
                _speichere_routinen(daten, username)
                return f"✅ Routine '{r['name']}' aktualisiert."
        return f"Routine mit ID {routine_id} nicht gefunden."
    
    # ─── SCHEDULER ───
    if "scheduler" in clean:
        if "start" in clean:
            return starte_scheduler()
        if "stopp" in clean:
            return stoppe_scheduler()
        return "Scheduler: 'scheduler start' oder 'scheduler stopp'"

    # ─── NEUE ROUTINE ───
    try:
        parts = clean.split("routine", 1)[-1].strip()
        aktionen = []
        wochentage = None

        match = _RE_WOCHENTAGE.search(parts)
        if match:
            wochentag_str = match.group(1).strip().lower()
            parts = parts.replace(match.group(0), "").strip()
            if wochentag_str in ("werktags", "werktage"):
                wochentage = ["mo", "di", "mi", "do", "fr"]
            elif wochentag_str in ("wochenende", "wochenenden"):
                wochentage = ["sa", "so"]
            else:
                wochentage = [tag.strip()[:2] for tag in re.split(r'[,\s]+', wochentag_str) if tag.strip()]
                wochentage = [tag[:2] for tag in wochentage if tag]
                valid = ["mo", "di", "mi", "do", "fr", "sa", "so"]
                wochentage = [t for t in wochentage if t in valid]

        if "|" in parts:
            parts_list = _RE_ROUTINE_SPLIT.split(parts)
            name_trigger = parts_list[0].strip()
            aktionen = [a.strip() for a in parts_list[1:] if a.strip()]
        else:
            name_trigger = parts
            aktionen = []

        if "sprache" in name_trigger:
            trigger = "sprache"
            name = name_trigger.split("sprache")[0].strip()
            trigger_wert = name_trigger.split("sprache")[1].strip().split("|")[0].strip()
            if not trigger_wert:
                return "Bitte gib einen Trigger-Text an: 'routine Guten Morgen sprache guten morgen | sag Hallo'"
        elif "zeit" in name_trigger:
            trigger = "zeit"
            name = name_trigger.split("zeit")[0].strip()
            trigger_wert = name_trigger.split("zeit")[1].strip().split("|")[0].strip()
            if not trigger_wert or not _RE_ZEIT.match(trigger_wert):
                return "Bitte gib eine Uhrzeit an: 'routine Nacht zeit 22:00 | licht aus'"
            if not _validate_time(trigger_wert):
                return "❌ Ungültige Uhrzeit. Format: HH:MM (z.B. 14:30)"
        else:
            return "Trigger muss 'sprache' oder 'zeit' sein."

        if not name or not trigger_wert:
            return "Bitte gib einen Namen und Trigger-Wert an."
        if not aktionen:
            return "Bitte gib mindestens eine Aktion an."

        return routine_hinzufuegen(name, trigger, trigger_wert, aktionen, wochentage=wochentage, username=username)
    except Exception as e:
        logging.error(f"Routine Fehler: {e}")
        return f"Fehler beim Erstellen der Routine: {e}"

def tools_holen():
    return [
        ("routine_hinzufuegen", routine_hinzufuegen, "Routinen"),
        ("routine_loeschen", routine_loeschen, "Routinen"),
        ("routine_toggle", routine_toggle, "Routinen"),
        ("routine_aktualisieren", routine_aktualisieren, "Routinen"),
        ("routinen_alle", routinen_alle, "Routinen"),
        ("routine_ausfuehren", routine_ausfuehren, "Routinen"),
        ("starte_scheduler", starte_scheduler, "Routinen"),
        ("stoppe_scheduler", stoppe_scheduler, "Routinen"),
    ]