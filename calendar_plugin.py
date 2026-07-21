# plugins/calendar_plugin.py – Kalender, Erinnerungen, Timer

import re
import threading
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from utils import lade_json, speichere_json, send_notification, logging

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

def register(core):
    core.register_command(["termin", "erinnerung", "timer"], handle_calendar, "Termine & Erinnerungen verwalten")

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
    return f"kalender_{username}.json"

def _get_wochentag(datum_str):
    try:
        dt = datetime.strptime(datum_str, "%Y-%m-%d")
        return WOCHENTAGE[dt.weekday()]
    except:
        return "Unbekannt"

def _naechstes_datum(text):
    heute = datetime.now().date()
    if "heute" in text:
        return heute.strftime("%Y-%m-%d")
    elif "morgen" in text:
        return (heute + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "übermorgen" in text:
        return (heute + timedelta(days=2)).strftime("%Y-%m-%d")
    return None

def termin_hinzufuegen(titel, datum=None, uhrzeit=None, ort="", notiz="", username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    if "termine" not in daten:
        daten["termine"] = []
    if not datum:
        for w in ["heute", "morgen", "übermorgen"]:
            if w in titel.lower():
                datum = _naechstes_datum(w)
                titel = titel.lower().replace(w, "").strip()
                break
        if not datum:
            m = re.search(r'(\d{4}-\d{2}-\d{2})', titel)
            if m:
                datum = m.group(1)
                titel = titel.replace(m.group(1), "").strip()
            else:
                return "Bitte gib ein Datum an."
    try:
        datetime.strptime(datum, "%Y-%m-%d")
    except:
        return f"Ungültiges Datum: {datum}. Format: YYYY-MM-DD"
    if not uhrzeit:
        m = re.search(r'(\d{1,2}:\d{2})', titel)
        if m:
            uhrzeit = m.group(1)
            titel = titel.replace(m.group(1), "").strip()
        else:
            uhrzeit = "08:00"
    try:
        datetime.strptime(uhrzeit, "%H:%M")
    except:
        return f"Ungültige Uhrzeit: {uhrzeit}. Format: HH:MM"
    wochentag = _get_wochentag(datum)
    neue_id = max([t.get("id", 0) for t in daten["termine"]], default=0) + 1
    termin = {
        "id": neue_id,
        "titel": titel.strip(),
        "datum": datum,
        "uhrzeit": uhrzeit,
        "wochentag": wochentag,
        "ort": ort.strip() if ort else "",
        "notiz": notiz.strip() if notiz else "",
        "erstellt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "offen",
        "typ": "termin",
        "benachrichtigt": False
    }
    daten["termine"].append(termin)
    speichere_json(file, daten)
    msg = f"Termin hinzugefügt: {termin['titel']} am {wochentag}, {datum} um {uhrzeit} Uhr"
    if termin["ort"]:
        msg += f" in {termin['ort']}"
    send_notification("Neuer Termin", msg)
    return msg

def erinnerung_hinzufuegen(titel, datum=None, uhrzeit=None, username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    if "termine" not in daten:
        daten["termine"] = []
    if not datum:
        if "heute" in titel.lower():
            datum = datetime.now().strftime("%Y-%m-%d")
            titel = titel.lower().replace("heute", "").strip()
        elif "morgen" in titel.lower():
            datum = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            titel = titel.lower().replace("morgen", "").strip()
        else:
            datum = datetime.now().strftime("%Y-%m-%d")
    if not uhrzeit:
        m = re.search(r'(\d{1,2}:\d{2})', titel)
        if m:
            uhrzeit = m.group(1)
            titel = titel.replace(m.group(1), "").strip()
        else:
            uhrzeit = datetime.now().strftime("%H:%M")
    wochentag = _get_wochentag(datum)
    neue_id = max([t.get("id", 0) for t in daten["termine"]], default=0) + 1
    erinnerung = {
        "id": neue_id,
        "titel": titel.strip(),
        "datum": datum,
        "uhrzeit": uhrzeit,
        "wochentag": wochentag,
        "ort": "",
        "notiz": "",
        "erstellt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "offen",
        "typ": "erinnerung",
        "benachrichtigt": False
    }
    daten["termine"].append(erinnerung)
    speichere_json(file, daten)
    msg = f"Erinnerung gesetzt: {erinnerung['titel']} am {wochentag}, {datum} um {uhrzeit} Uhr"
    send_notification("Neue Erinnerung", msg)
    return msg

def termine_heute(username=None):
    file = _get_user_file(username)
    heute = datetime.now().strftime("%Y-%m-%d")
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    heute_termine = [t for t in termine if t.get("datum") == heute]
    if not heute_termine:
        return "Heute keine Termine oder Erinnerungen."
    heute_termine.sort(key=lambda x: x.get("uhrzeit", "00:00"))
    ausgabe = "Heute:\n"
    for t in heute_termine:
        typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
        status = "✓" if t.get("status") == "erledigt" else "○"
        ausgabe += f"  {status} {typ} {t.get('uhrzeit','??:??')} – {t.get('titel','?')}"
        if t.get("ort"):
            ausgabe += f" ({t['ort']})"
        ausgabe += f" [ID:{t.get('id')}]\n"
    return ausgabe.strip()

def termine_alle(username=None):
    file = _get_user_file(username)
    heute = datetime.now().strftime("%Y-%m-%d")
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    zukunft = [t for t in termine if t.get("datum") >= heute and t.get("status") != "erledigt"]
    zukunft.sort(key=lambda x: (x.get("datum", "9999-99-99"), x.get("uhrzeit", "99:99")))
    if not zukunft:
        return "Keine zukünftigen Einträge."
    ausgabe = "Alle Termine & Erinnerungen:\n"
    for t in zukunft[:15]:
        typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
        status = "✓" if t.get("status") == "erledigt" else "○"
        ausgabe += f"  {status} {typ} {t.get('datum','?')} {t.get('uhrzeit','?')} – {t.get('titel','?')} [ID:{t.get('id')}]\n"
    return ausgabe.strip()

def termin_loeschen(termin_id, username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    for i, t in enumerate(termine):
        if t.get("id") == termin_id:
            titel = t.get("titel", "?")
            typ = t.get("typ", "termin")
            del termine[i]
            daten["termine"] = termine
            speichere_json(file, daten)
            return f"'{titel}' ({typ}) gelöscht."
    return f"Eintrag mit ID {termin_id} nicht gefunden."

def erinnerung_loeschen(erinnerung_id, username=None):
    return termin_loeschen(erinnerung_id, username)

def termin_erledigen(termin_id, username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    for t in termine:
        if t.get("id") == termin_id:
            t["status"] = "erledigt"
            daten["termine"] = termine
            speichere_json(file, daten)
            return f"'{t.get('titel','?')}' als erledigt markiert."
    return f"Eintrag mit ID {termin_id} nicht gefunden."

def termin_suche(suchbegriff, username=None):
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    suchbegriff = suchbegriff.lower()
    treffer = [t for t in termine if suchbegriff in t.get("titel", "").lower() or suchbegriff in t.get("ort", "").lower()]
    if not treffer:
        return f"Keine Einträge mit '{suchbegriff}' gefunden."
    ausgabe = f"'{suchbegriff}':\n"
    for t in treffer[:10]:
        typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
        ausgabe += f"  {typ} ID {t.get('id')}: {t.get('datum','?')} {t.get('uhrzeit','?')} – {t.get('titel','?')}\n"
    return ausgabe.strip()

def termin_naechster(username=None):
    file = _get_user_file(username)
    heute = datetime.now().strftime("%Y-%m-%d")
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    zukunft = [t for t in termine if t.get("datum") >= heute and t.get("status") != "erledigt"]
    if not zukunft:
        return "Keine anstehenden Termine."
    zukunft.sort(key=lambda x: (x.get("datum", "9999-99-99"), x.get("uhrzeit", "99:99")))
    t = zukunft[0]
    typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
    return f"Nächster {typ} {t.get('titel','?')} am {t.get('wochentag','?')}, {t.get('datum','?')} um {t.get('uhrzeit','?')} Uhr."

def termine_vorschau(anzahl=3, username=None):
    file = _get_user_file(username)
    heute = datetime.now().strftime("%Y-%m-%d")
    daten = lade_json(file, {"termine": []})
    zukunft = [t for t in daten.get("termine", []) if t.get("datum") >= heute and t.get("status") != "erledigt"]
    zukunft.sort(key=lambda x: (x.get("datum", "9999-99-99"), x.get("uhrzeit", "99:99")))
    if not zukunft:
        return "Keine anstehenden Termine."
    ausgabe = "Nächste Termine:\n"
    for t in zukunft[:anzahl]:
        typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
        ausgabe += f"  {typ} {t.get('datum','?')} {t.get('uhrzeit','?')} – {t.get('titel','?')} [ID:{t.get('id')}]\n"
    return ausgabe.strip()

def timer_mit_erinnerung(minuten: int, text: str):
    if minuten <= 0:
        return "Die Minutenanzahl muss größer als 0 sein."
    sekunden = minuten * 60
    def callback():
        send_notification("Timer", f"Erinnerung: {text}")
    t = threading.Timer(sekunden, callback)
    t.daemon = True
    t.start()
    return f"Timer für {minuten} Minute(n) gestartet. Ich erinnere dich an: {text}"

_timer_threads = []

def timer_setzen(sekunden, nachricht="Timer abgelaufen"):
    def timer_abgelaufen():
        send_notification("Timer", nachricht)
    t = threading.Timer(sekunden, timer_abgelaufen)
    t.daemon = True
    t.start()
    _timer_threads.append(t)
    return f"Timer für {sekunden} Sekunden gestartet."

def timer_abbrechen():
    for t in _timer_threads:
        if t.is_alive():
            t.cancel()
    _timer_threads.clear()
    return "Alle Timer abgebrochen."

def termine_monat(year=None, month=None, username=None):
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month
    file = _get_user_file(username)
    daten = lade_json(file, {"termine": []})
    termine = daten.get("termine", [])
    month_terms = []
    for t in termine:
        try:
            t_date = datetime.strptime(t.get("datum", "1970-01-01"), "%Y-%m-%d")
            if t_date.year == year and t_date.month == month:
                month_terms.append(t)
        except:
            pass
    month_terms.sort(key=lambda x: (x.get("datum", "9999-99-99"), x.get("uhrzeit", "99:99")))
    return month_terms

def handle_calendar(befehl):
    """Verarbeitet alle Kalender-Befehle."""
    clean = befehl.lower().strip()
    username = _get_current_user()

    # Termin heute
    if "termin" in clean:
        if "heute" in clean and not any(w in clean for w in ["alle", "erledigen", "löschen", "loeschen", "suche"]):
            return termine_heute(username)
        if "alle" in clean:
            return termine_alle(username)
        if "erledigen" in clean:
            match = re.search(r'erledigen\s+(\d+)', clean)
            if match:
                return termin_erledigen(int(match.group(1)), username)
            return "Bitte gib eine ID an: 'termin erledigen 5'"
        if "löschen" in clean or "loeschen" in clean:
            match = re.search(r'(?:löschen|loeschen)\s+(\d+)', clean)
            if match:
                return termin_loeschen(int(match.group(1)), username)
            return "Bitte gib eine ID an: 'termin löschen 5'"
        if "suche" in clean:
            suchbegriff = clean.split("suche", 1)[-1].strip()
            if suchbegriff:
                return termin_suche(suchbegriff, username)
            return "Bitte gib einen Suchbegriff an: 'termin suche Zahnarzt'"

        # Neuen Termin anlegen
        parts = clean.split(maxsplit=1)
        if len(parts) < 2:
            return "Format: 'termin <Titel> <YYYY-MM-DD> <HH:MM> [Ort]'"
        text = parts[1]
        datum_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if not datum_match:
            if "heute" in text:
                datum = datetime.now().strftime("%Y-%m-%d")
            elif "morgen" in text:
                datum = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "übermorgen" in text:
                datum = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                return "Bitte gib ein Datum an (YYYY-MM-DD) oder 'heute', 'morgen', 'übermorgen'"
        else:
            datum = datum_match.group(1)
            text = text.replace(datum_match.group(1), "").strip()
        uhrzeit_match = re.search(r'(\d{1,2}:\d{2})', text)
        if uhrzeit_match:
            uhrzeit = uhrzeit_match.group(1)
            text = text.replace(uhrzeit_match.group(1), "").strip()
        else:
            uhrzeit = "08:00"
        ort_match = re.search(r'\(([^)]+)\)', text)
        if ort_match:
            ort = ort_match.group(1)
            text = text.replace(f"({ort})", "").strip()
        else:
            ort = ""
        titel = re.sub(r'\b(um|am|uhr|Uhr)\b', '', text).strip()
        if not titel:
            return "Bitte gib einen Titel für den Termin an."
        return termin_hinzufuegen(titel, datum, uhrzeit, ort, username=username)

    # Erinnerung
    if "erinnerung" in clean:
        if "löschen" in clean or "loeschen" in clean:
            match = re.search(r'(?:löschen|loeschen)\s+(\d+)', clean)
            if match:
                return erinnerung_loeschen(int(match.group(1)), username)
            return "Bitte gib eine ID an: 'erinnerung löschen 5'"
        text = clean.split("erinnerung", 1)[-1].strip()
        if not text:
            return "Was soll ich dir merken?"
        datum = None
        uhrzeit = None
        if "heute" in text:
            datum = datetime.now().strftime("%Y-%m-%d")
            text = text.replace("heute", "").strip()
        elif "morgen" in text:
            datum = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            text = text.replace("morgen", "").strip()
        else:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            if match:
                datum = match.group(1)
                text = text.replace(match.group(1), "").strip()
        match = re.search(r'(\d{1,2}:\d{2})', text)
        if match:
            uhrzeit = match.group(1)
            text = text.replace(match.group(1), "").strip()
        titel = text.strip()
        if not titel:
            return "Bitte gib einen Titel für die Erinnerung an."
        return erinnerung_hinzufuegen(titel, datum, uhrzeit, username)

    # Nächster Termin
    if "nächster termin" in clean or "nächsten termin" in clean or "wann habe ich" in clean:
        return termin_naechster(username)

    # Vorschau
    if any(phrase in clean for phrase in ["nächste termine", "vorschau", "nächste 3 termine"]):
        return termine_vorschau(anzahl=3, username=username)

    # Timer
    if "erinnere mich in" in clean and "minuten" in clean:
        match = re.search(r'erinnere mich in (\d+)\s*minuten?\s+an\s+(.+)', clean)
        if match:
            minuten = int(match.group(1))
            text = match.group(2).strip()
            return timer_mit_erinnerung(minuten, text)
        return "Bitte gib an: 'erinnere mich in 5 Minuten an Müll rausbringen'"

    return "Kalender-Befehl nicht erkannt. Hilfe: 'termin', 'erinnerung', 'timer'"