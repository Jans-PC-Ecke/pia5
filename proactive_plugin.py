# plugins/proactive_plugin.py – Proaktive Vorschläge mit behavior-Integration & Gewichtung

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from utils import lade_json, logging, send_notification
from plugins.memory_plugin import get_facts

def register(core):
    core.register_command(
        ["proaktiv", "vorschläge", "analyse", "erinnerungen"],
        handle_proactive,
        "Proaktive Vorschläge aus deinen Daten"
    )

# ─── HELFER ───
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

def _get_behavior_patterns(username=None):
    """Holt Muster aus behavior_plugin – mit Gewichtung."""
    try:
        from plugins.behavior_plugin import analyze_behavior
        # Wir rufen nur die Analyse auf, aber ohne Push
        result = analyze_behavior(username=username)
        # Parsen der Muster aus der Ausgabe (vereinfacht)
        if "Neue Muster erkannt" in result:
            # Extrahiere die Muster aus dem Text (vereinfacht)
            patterns = []
            lines = result.split("\n")
            for line in lines:
                if line.strip().startswith("•") or re.search(r'\d+\.', line):
                    patterns.append(line.strip())
            return patterns
    except Exception as e:
        logging.debug(f"Behavior-Integration nicht verfügbar: {e}")
    return []

# ─── ANALYSE-FUNKTIONEN ───
def analyze_facts(username="jan"):
    facts = get_facts(username=username)
    if not facts:
        return []

    suggestions = []
    fact_texts = [f["fact"].lower() for f in facts]

    food_keywords = ["pizza", "käse", "milch", "brot", "ei", "nudel", "reis", "fleisch", "gemüse"]
    food_facts = [f for f in fact_texts if any(kw in f for kw in food_keywords)]
    if len(food_facts) >= 2:
        suggestions.append({
            "type": "einkaufsliste",
            "title": "🍕 Essens-Fakten erkannt!",
            "description": f"Du hast {len(food_facts)} Essens-Fakten. Soll ich sie zur Einkaufsliste hinzufügen?",
            "action": "einkaufsliste_hinzufuegen",
            "items": food_facts,
            "weight": len(food_facts) * 2  # Gewichtung basierend auf Anzahl
        })

    date_keywords = ["geburtstag", "termin", "meeting", "arzt", "zahnarzt", "urlaub"]
    date_facts = [f for f in fact_texts if any(kw in f for kw in date_keywords)]
    if date_facts:
        suggestions.append({
            "type": "kalender",
            "title": "📅 Termin-Fakten erkannt!",
            "description": f"Du hast {len(date_facts)} Termin-Fakten. Soll ich sie in den Kalender eintragen?",
            "action": "kalender_hinzufuegen",
            "items": date_facts,
            "weight": len(date_facts) * 3  # Termine haben höhere Priorität
        })

    routine_keywords = ["morgens", "abends", "immer", "jeden tag", "wöchentlich"]
    routine_facts = [f for f in fact_texts if any(kw in f for kw in routine_keywords)]
    if routine_facts:
        suggestions.append({
            "type": "routine",
            "title": "🔄 Routinen-Fakten erkannt!",
            "description": f"Du hast {len(routine_facts)} Routinen-Fakten. Soll ich sie als Routine einrichten?",
            "action": "routine_erstellen",
            "items": routine_facts,
            "weight": len(routine_facts) * 2
        })

    if len(facts) >= 10:
        suggestions.append({
            "type": "zusammenfassung",
            "title": "📖 Dein Gedächtnis wächst!",
            "description": f"Du hast {len(facts)} Fakten gespeichert. Nutze 'suche <begriff>' für Details.",
            "action": None,
            "items": [],
            "weight": 1
        })

    return suggestions

def analyze_calendar(username="jan"):
    try:
        from plugins.calendar_plugin import termine_heute, termine_alle
        today = termine_heute(username=username)
        all_terms = termine_alle(username=username)
    except:
        return []

    suggestions = []
    if "Keine" not in today and today:
        suggestions.append({
            "type": "kalender",
            "title": "📅 Heutige Termine",
            "description": today,
            "action": None,
            "items": [],
            "weight": 5  # Heutige Termine haben höchste Priorität
        })
    if all_terms and "Keine" not in all_terms:
        suggestions.append({
            "type": "kalender",
            "title": "📅 Anstehende Termine",
            "description": all_terms[:100] + "..." if len(all_terms) > 100 else all_terms,
            "action": None,
            "items": [],
            "weight": 3
        })
    return suggestions

def analyze_shopping(username="jan"):
    try:
        from plugins.shopping_plugin import einkaufsliste_anzeigen
        list_text = einkaufsliste_anzeigen(username=username)
    except:
        return []

    suggestions = []
    if "leer" in list_text.lower():
        suggestions.append({
            "type": "einkaufsliste",
            "title": "🛒 Einkaufsliste ist leer!",
            "description": "Deine Einkaufsliste ist leer. Möchtest du etwas hinzufügen?",
            "action": None,
            "items": [],
            "weight": 2
        })
    else:
        items = [line.strip() for line in list_text.split("\n") if line.strip() and "-" in line]
        if len(items) >= 5:
            suggestions.append({
                "type": "einkaufsliste",
                "title": f"🛒 {len(items)} Artikel auf der Liste",
                "description": f"Du hast {len(items)} Artikel. Vergiss sie nicht beim Einkauf!",
                "action": None,
                "items": items,
                "weight": len(items)
            })
    return suggestions

# ─── BEHAVIOR-INTEGRATION ───
def analyze_behavior_patterns(username="jan"):
    """Analysiert Verhaltensmuster und gibt gewichtete Vorschläge."""
    patterns = _get_behavior_patterns(username)
    if not patterns:
        return []
    
    suggestions = []
    for p in patterns[:3]:
        suggestions.append({
            "type": "verhalten",
            "title": "🧠 Verhaltensmuster erkannt!",
            "description": p,
            "action": "routine_erstellen",
            "items": [],
            "weight": 4  # Verhaltensmuster haben hohe Priorität
        })
    return suggestions

# ─── HAUPTFUNKTION ───
def get_all_suggestions(username="jan"):
    """Sammelt alle Vorschläge mit Gewichtung und sortiert sie."""
    all_suggestions = []
    all_suggestions.extend(analyze_facts(username))
    all_suggestions.extend(analyze_calendar(username))
    all_suggestions.extend(analyze_shopping(username))
    all_suggestions.extend(analyze_behavior_patterns(username))
    
    # Sortieren nach Gewicht (höchste zuerst)
    all_suggestions.sort(key=lambda x: x.get("weight", 0), reverse=True)
    return all_suggestions

def handle_proactive(befehl):
    clean = befehl.lower().strip()

    if "vorschläge" in clean or "vorschlag" in clean:
        suggestions = get_all_suggestions()
        if not suggestions:
            return "🔍 Keine neuen Vorschläge. Dein System ist im Gleichgewicht!"

        ausgabe = "💡 **Proaktive Vorschläge (nach Wichtigkeit):**\n\n"
        for i, s in enumerate(suggestions, 1):
            ausgabe += f"{i}. {s['title']}\n   {s['description']}\n"
            if s.get("items"):
                ausgabe += f"   → {', '.join(s['items'][:3])}\n"
            if s.get("weight"):
                ausgabe += f"   📊 Priorität: {s['weight']}\n"
            ausgabe += "\n"
        return ausgabe.strip()

    if "analyse" in clean:
        return "📊 **Analyse gestartet.** Vorschläge werden in Kürze angezeigt (nutze 'vorschläge')."

    return "Proaktive Befehle: 'vorschläge', 'analyse'"

# ─── TOOLS ───
def tools_holen():
    return [
        ("get_all_suggestions", get_all_suggestions, "Alle Vorschläge mit Gewichtung"),
        ("analyze_facts", analyze_facts, "Fakten analysieren"),
        ("analyze_calendar", analyze_calendar, "Kalender analysieren"),
        ("analyze_shopping", analyze_shopping, "Einkaufsliste analysieren"),
        ("analyze_behavior_patterns", analyze_behavior_patterns, "Verhaltensmuster analysieren"),
    ]