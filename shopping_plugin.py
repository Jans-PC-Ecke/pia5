# plugins/shopping_plugin.py – Einkaufsliste (vollständig)

import re
import json
from pathlib import Path
from utils import lade_json, speichere_json

def register(core):
    core.register_command(
        ["einkaufsliste", "einkauf", "shopping"],
        handle_shopping,
        "Einkaufsliste mit Mengen"
    )

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
    return f"shopping_{username}.json"

def einkaufsliste_hinzufuegen(item, menge="1", einheit="", username=None):
    """Fügt einen Artikel zur Einkaufsliste hinzu."""
    file = _get_user_file(username)
    daten = lade_json(file, {"items": []})
    
    # Prüfe, ob der Artikel bereits existiert (dann Menge erhöhen)
    existing = None
    for entry in daten["items"]:
        if entry.get("name", "").lower() == item.lower() and not entry.get("erledigt", False):
            existing = entry
            break
    
    if existing:
        try:
            neue_menge = int(existing.get("menge", "1")) + int(menge)
            existing["menge"] = str(neue_menge)
            speichere_json(file, daten)
            return f"'{item}' bereits auf der Liste – Menge auf {neue_menge} erhöht."
        except:
            pass
    
    neue_id = max([i.get("id", 0) for i in daten["items"]], default=0) + 1
    daten["items"].append({
        "id": neue_id,
        "name": item.strip(),
        "menge": menge,
        "einheit": einheit,
        "erledigt": False
    })
    speichere_json(file, daten)
    return f"'{item}' ({menge}{einheit}) zur Einkaufsliste hinzugefügt."

def einkaufsliste_entfernen(item_oder_id, username=None):
    """Entfernt einen Artikel von der Einkaufsliste – unterstützt ID oder Name."""
    file = _get_user_file(username)
    daten = lade_json(file, {"items": []})
    
    # Versuche als ID zu parsen
    try:
        id_ = int(item_oder_id)
        for i, entry in enumerate(daten["items"]):
            if entry.get("id") == id_:
                name = entry.get("name", "?")
                del daten["items"][i]
                speichere_json(file, daten)
                return f"'{name}' von der Liste entfernt."
        return f"ID {id_} nicht gefunden."
    except ValueError:
        # Als Name behandeln
        item_name = item_oder_id.strip().lower()
        for i, entry in enumerate(daten["items"]):
            if entry.get("name", "").lower() == item_name:
                del daten["items"][i]
                speichere_json(file, daten)
                return f"'{item_oder_id}' von der Liste entfernt."
        return f"'{item_oder_id}' nicht in der Liste."

def einkaufsliste_anzeigen(username=None):
    """Zeigt die Einkaufsliste an."""
    file = _get_user_file(username)
    daten = lade_json(file, {"items": []})
    items = [i for i in daten.get("items", []) if not i.get("erledigt", False)]
    if not items:
        return "Einkaufsliste ist leer."
    ausgabe = "Einkaufsliste:\n"
    for i in items:
        menge = i.get("menge", "1")
        einheit = i.get("einheit", "")
        ausgabe += f"  - {menge}{einheit} {i.get('name')} [ID:{i.get('id')}]\n"
    return ausgabe.strip()

def einkaufsliste_erledigt(item_oder_id, username=None):
    """Markiert einen Artikel als erledigt – unterstützt ID oder Name."""
    file = _get_user_file(username)
    daten = lade_json(file, {"items": []})
    
    try:
        id_ = int(item_oder_id)
        for entry in daten["items"]:
            if entry.get("id") == id_:
                entry["erledigt"] = True
                speichere_json(file, daten)
                return f"'{entry.get('name')}' als erledigt markiert."
        return f"ID {id_} nicht gefunden."
    except ValueError:
        item_name = item_oder_id.strip().lower()
        for entry in daten["items"]:
            if entry.get("name", "").lower() == item_name:
                entry["erledigt"] = True
                speichere_json(file, daten)
                return f"'{item_oder_id}' als erledigt markiert."
        return f"'{item_oder_id}' nicht gefunden."

def einkaufsliste_leeren(username=None):
    """Leert die gesamte Einkaufsliste."""
    file = _get_user_file(username)
    speichere_json(file, {"items": []})
    return "Einkaufsliste geleert."

def handle_shopping(befehl):
    """Hauptfunktion für alle Shopping-Befehle."""
    clean = befehl.lower().strip()
    username = _get_current_user()

    # ─── WENN NUR EIN WORT → HINZUFÜGEN ───
    if len(clean.split()) == 1 and clean not in ["einkaufsliste", "liste", "leeren", "clear", "einkauf", "shopping"]:
        return einkaufsliste_hinzufuegen(clean, "1", "", username)

    # ─── LÖSCHEN ───
    if any(w in clean for w in ["entfernen", "löschen", "delete", "remove"]):
        match = re.search(r'(?:entfernen|löschen|delete|remove)\s+(\d+)', clean)
        if match:
            return einkaufsliste_entfernen(int(match.group(1)), username)
        match = re.search(r'(?:entfernen|löschen|delete|remove)\s+(.+)$', clean)
        if match:
            item = match.group(1).strip()
            item = re.sub(r'\s*von\s+der\s+(?:einkaufs)?liste$', '', item)
            if item:
                return einkaufsliste_entfernen(item, username)
        return "Bitte gib an: 'lösche 1' oder 'lösche Milch'"

    # ─── ERLEDIGT ───
    if any(w in clean for w in ["erledigt", "abgehakt", "done"]):
        match = re.search(r'(?:erledigt|abgehakt|done)\s+(\d+)', clean)
        if match:
            return einkaufsliste_erledigt(int(match.group(1)), username)
        match = re.search(r'(?:erledigt|abgehakt|done)\s+(.+)$', clean)
        if match:
            item = match.group(1).strip()
            item = re.sub(r'\s*von\s+der\s+(?:einkaufs)?liste$', '', item)
            if item:
                return einkaufsliste_erledigt(item, username)
        return "Bitte gib an: 'erledigt 1' oder 'erledigt Milch'"

    # ─── HINZUFÜGEN ───
    if any(w in clean for w in ["hinzufügen", "füge hinzu", "add", "neu"]):
        match = re.match(r'^(\d+)\s*(x|stk|kg|g|ml|l|packung|flasche)?\s+(.+)$', clean)
        if match:
            menge = match.group(1)
            einheit = match.group(2) or ""
            item = match.group(3).strip()
            return einkaufsliste_hinzufuegen(item, menge, einheit, username)
        match = re.search(r'(?:hinzufügen|füge hinzu|add|neu)\s+(.+?)(?:\s+zur\s+einkaufsliste)?$', clean)
        if not match:
            match = re.search(r'einkaufsliste\s+(?:hinzufügen|add)\s+(.+)', clean)
        if match:
            item = match.group(1).strip()
            if item:
                return einkaufsliste_hinzufuegen(item, "1", "", username)
        return "Bitte gib einen Artikel an: 'füge Milch hinzu' oder '2x Eier'"

    # ─── LEEREN ───
    if any(w in clean for w in ["leer", "leeren", "clear"]):
        return einkaufsliste_leeren(username)

    # ─── ANZEIGEN (Standard) ───
    return einkaufsliste_anzeigen(username)

def tools_holen():
    return [
        ("einkaufsliste_hinzufuegen", einkaufsliste_hinzufuegen, "Einkaufsliste"),
        ("einkaufsliste_entfernen", einkaufsliste_entfernen, "Einkaufsliste"),
        ("einkaufsliste_anzeigen", einkaufsliste_anzeigen, "Einkaufsliste"),
        ("einkaufsliste_erledigt", einkaufsliste_erledigt, "Einkaufsliste"),
        ("einkaufsliste_leeren", einkaufsliste_leeren, "Einkaufsliste"),
    ]