# plugins/daily_plugin.py – Tägliche Übersicht: Termine + Einkauf + Offene Aufgaben

import re
from datetime import datetime
from utils import logging

def register(core):
    core.register_command(
        ["daily", "heute", "übersicht", "was muss ich"],
        handle_daily,
        "Tägliche Übersicht (Termine + Einkauf + Aufgaben)"
    )

def _get_current_user():
    try:
        import json
        from pathlib import Path
        active_file = Path("active_user.json")
        if active_file.exists():
            with open(active_file, "r") as f:
                data = json.load(f)
            return data.get("username", "jan")
    except:
        pass
    return "jan"

def _get_today_appointments(username=None):
    """Holt die heutigen Termine aus dem Kalender."""
    try:
        from plugins.calendar_plugin import termine_heute
        result = termine_heute(username=username)
        if "Keine" in result:
            return []
        # Parse die Ausgabe
        lines = result.split("\n")
        items = []
        for line in lines:
            if line.strip() and "–" in line:
                parts = line.split("–")
                if len(parts) >= 2:
                    typ = "Erinnerung" if "Erinnerung" in line else "Termin"
                    status = "✓" if "✓" in line else "○"
                    items.append({
                        "typ": typ,
                        "status": status,
                        "text": parts[1].strip() if len(parts) > 1 else line.strip()
                    })
        return items
    except Exception as e:
        logging.error(f"Daily - Calendar Fehler: {e}")
        return []

def _get_today_shopping(username=None):
    """Holt die Einkaufsliste."""
    try:
        from plugins.shopping_plugin import einkaufsliste_anzeigen
        result = einkaufsliste_anzeigen(username=username)
        if "leer" in result.lower():
            return []
        # Extrahiere Items
        items = []
        for line in result.split("\n"):
            if line.strip() and "-" in line:
                match = re.search(r'-\s+(.+?)\s*\[ID:(\d+)\]', line)
                if match:
                    items.append({
                        "text": match.group(1).strip(),
                        "id": match.group(2)
                    })
                else:
                    items.append({"text": line.strip(), "id": None})
        return items
    except Exception as e:
        logging.error(f"Daily - Shopping Fehler: {e}")
        return []

def _get_offene_aufgaben(username=None):
    """Holt offene Aufgaben aus dem Gedächtnis (Fakten mit 'zu erledigen')."""
    try:
        from plugins.memory_plugin import get_facts
        facts = get_facts(query="zu erledigen", username=username, limit=10)
        tasks = []
        for f in facts:
            if "zu erledigen" in f["fact"].lower() or "aufgabe" in f["fact"].lower():
                tasks.append(f["fact"])
        return tasks
    except Exception as e:
        logging.error(f"Daily - Tasks Fehler: {e}")
        return []

def handle_daily(befehl):
    """Erstellt eine tägliche Übersicht."""
    username = _get_current_user()
    heute = datetime.now().strftime("%A, %d. %B %Y")
    
    # ─── 1. TERMINE ───
    termine = _get_today_appointments(username)
    
    # ─── 2. EINKAUFSLISTE ───
    einkauf = _get_today_shopping(username)
    
    # ─── 3. OFFENE AUFGABEN ───
    aufgaben = _get_offene_aufgaben(username)
    
    # ─── AUSGABE ───
    ausgabe = f"📋 **Tägliche Übersicht – {heute}**\n\n"
    
    # Termine
    ausgabe += "📅 **Termine heute:**\n"
    if termine:
        for t in termine:
            ausgabe += f"  {t['status']} {t['typ']}: {t['text']}\n"
    else:
        ausgabe += "  ✅ Keine Termine heute.\n"
    
    ausgabe += "\n"
    
    # Einkaufsliste
    ausgabe += "🛒 **Einkaufsliste:**\n"
    if einkauf:
        for item in einkauf:
            ausgabe += f"  - {item['text']}"
            if item['id']:
                ausgabe += f" [ID:{item['id']}]"
            ausgabe += "\n"
    else:
        ausgabe += "  ✅ Einkaufsliste ist leer.\n"
    
    ausgabe += "\n"
    
    # Offene Aufgaben
    ausgabe += "📌 **Offene Aufgaben:**\n"
    if aufgaben:
        for a in aufgaben:
            ausgabe += f"  - {a}\n"
    else:
        ausgabe += "  ✅ Keine offenen Aufgaben.\n"
    
    # ─── STATISTIK ───
    ausgabe += "\n---\n"
    anzahl_termine = len(termine)
    anzahl_einkauf = len(einkauf)
    anzahl_aufgaben = len(aufgaben)
    ausgabe += f"📊 **Zusammenfassung:** {anzahl_termine} Termine, {anzahl_einkauf} Einkaufsitems, {anzahl_aufgaben} offene Aufgaben."
    
    if anzahl_termine == 0 and anzahl_einkauf == 0 and anzahl_aufgaben == 0:
        ausgabe += "\n\n🎉 Du hast heute nichts zu tun! Genieß den Tag!"
    
    return ausgabe

def tools_holen():
    return [
        ("handle_daily", handle_daily, "Tägliche Übersicht"),
        ("_get_today_appointments", _get_today_appointments, "Termine holen"),
        ("_get_today_shopping", _get_today_shopping, "Einkauf holen"),
        ("_get_offene_aufgaben", _get_offene_aufgaben, "Aufgaben holen"),
    ]