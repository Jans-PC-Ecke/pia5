# plugins/behavior_plugin.py – Verhaltensanalyse 2.0 mit integriertem Agentic-Modus
# Erkennt: Kontext-Muster, Sequenzen, Ausnahmen
# Fragt: Mit Kontext & Erklärung
# Lernmodi: frag_mich, mach_einfach, erklaer_mir, lern_still

import re
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path
from utils import lade_json, speichere_json, logging, send_notification

def register(core):
    core.register_command(
        ["verhalten", "muster", "analysiere", "kontext", "sequenz", "ausnahme",
         "agentic", "lernmodus", "modus", "feedback", "lerne"],
        handle_behavior,
        "Verhaltensanalyse 2.0 + Lernmodus"
    )

# ─── LERNDATEI ───
LEARNING_FILE = "behavior_learning.json"

def _load_learning():
    return lade_json(LEARNING_FILE, {
        "mode": "frag_mich",
        "accepted": [],
        "rejected": [],
        "auto_mode": False,
        "last_analysis": None,
        "pending": [],
        "learned_contexts": []
    })

def _save_learning(data):
    speichere_json(LEARNING_FILE, data)

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

def _get_memory(username=None):
    if username is None:
        username = _get_current_user()
    return lade_json(f"memory_{username}.json", {
        "facts": [],
        "activity_log": [],
        "conversations": [],
        "preferences": {}
    })

def _save_memory(data, username=None):
    if username is None:
        username = _get_current_user()
    speichere_json(f"memory_{username}.json", data)

def _get_context_string(context):
    if not context:
        return ""
    parts = []
    if context.get("pc_status"):
        parts.append(f"PC: {context['pc_status']}")
    if context.get("user_location"):
        parts.append(f"Ort: {context['user_location']}")
    if context.get("last_command"):
        parts.append(f"vorher: {context['last_command']}")
    return ", ".join(parts) if parts else ""

# ─── 1. KONTEXT-MUSTER ERKENNEN ───
def analyze_context_patterns(activities, min_occurrences=2):
    patterns = defaultdict(list)
    for activity in activities:
        command = activity.get("command")
        context = activity.get("context", {})
        if not command or not context:
            continue
        context_keys = []
        for key, value in context.items():
            if value:
                context_keys.append(f"{key}:{value}")
        if not context_keys:
            continue
        context_str = " & ".join(context_keys)
        key = f"{context_str} → {command}"
        patterns[key].append({
            "timestamp": activity.get("timestamp"),
            "command": command,
            "context": context
        })
    suggestions = []
    for key, entries in patterns.items():
        if len(entries) >= min_occurrences:
            context_str, command = key.split(" → ", 1)
            suggestions.append({
                "type": "kontext",
                "context": context_str,
                "command": command,
                "count": len(entries),
                "suggestion": f"Immer wenn {context_str}, machst du '{command}'",
                "routine_name": f"Auto_Kontext_{command.replace(' ', '_')}"
            })
    return suggestions

# ─── 2. SEQUENZ-MUSTER ERKENNEN ───
def analyze_sequence_patterns(activities, min_occurrences=2, max_gap=300):
    sequences = defaultdict(list)
    for i in range(len(activities) - 2):
        a1 = activities[i]
        a2 = activities[i+1]
        a3 = activities[i+2]
        cmd1 = a1.get("command")
        cmd2 = a2.get("command")
        cmd3 = a3.get("command")
        if not cmd1 or not cmd2 or not cmd3:
            continue
        try:
            t1 = datetime.fromisoformat(a1.get("timestamp", ""))
            t2 = datetime.fromisoformat(a2.get("timestamp", ""))
            t3 = datetime.fromisoformat(a3.get("timestamp", ""))
            gap1 = abs((t2 - t1).total_seconds())
            gap2 = abs((t3 - t2).total_seconds())
            if gap1 > max_gap or gap2 > max_gap:
                continue
        except:
            pass
        seq_key = f"{cmd1} → {cmd2} → {cmd3}"
        sequences[seq_key].append({
            "timestamp": a1.get("timestamp"),
            "day": a1.get("day")
        })
    suggestions = []
    for key, entries in sequences.items():
        if len(entries) >= min_occurrences:
            suggestions.append({
                "type": "sequenz",
                "sequence": key,
                "count": len(entries),
                "suggestion": f"Du machst oft '{key}' hintereinander",
                "routine_name": f"Auto_Sequenz_{key.replace(' → ', '_').replace(' ', '_')[:30]}"
            })
    return suggestions

# ─── 3. AUSNAHMEN ERKENNEN ───
def analyze_exceptions(activities, days_back=7):
    if len(activities) < 5:
        return []
    now = datetime.now()
    cutoff = now - timedelta(days=days_back)
    recent = [a for a in activities if datetime.fromisoformat(a.get("timestamp", "")) > cutoff]
    if len(recent) < 3:
        return []
    patterns = defaultdict(list)
    for activity in recent:
        hour = activity.get("hour")
        command = activity.get("command")
        day = activity.get("day")
        if hour is not None and command:
            key = f"{hour:02d}:00_{command}"
            patterns[key].append({
                "day": day,
                "timestamp": activity.get("timestamp")
            })
    suggestions = []
    for key, entries in patterns.items():
        if len(entries) >= 2:
            hour, command = key.split("_", 1)
            today = now.strftime("%Y-%m-%d")
            today_occurrences = [e for e in entries if e.get("timestamp", "").startswith(today)]
            if not today_occurrences:
                suggestions.append({
                    "type": "ausnahme",
                    "hour": hour,
                    "command": command,
                    "count": len(entries),
                    "suggestion": f"Normalerweise machst du um {hour} Uhr '{command}', aber heute noch nicht.",
                    "routine_name": None
                })
    return suggestions

# ─── 4. KONTEXT SPEICHERN ───
def log_context(command, context, username=None):
    if username is None:
        username = _get_current_user()
    memory = _get_memory(username)
    entry = {
        "command": command,
        "timestamp": datetime.now().isoformat(),
        "hour": datetime.now().hour,
        "day": datetime.now().weekday(),
        "context": context or {}
    }
    if "activity_log" not in memory:
        memory["activity_log"] = []
    memory["activity_log"].append(entry)
    if len(memory["activity_log"]) > 500:
        memory["activity_log"] = memory["activity_log"][-500:]
    _save_memory(memory, username)

# ─── 5. HAUPTANALYSE ───
def analyze_behavior(username=None, mode=None):
    if username is None:
        username = _get_current_user()
    memory = _get_memory(username)
    activities = memory.get("activity_log", [])
    if len(activities) < 3:
        return "📊 Noch nicht genug Daten. Nutze Pia häufiger, damit ich Muster erkennen kann."
    
    learning = _load_learning()
    current_mode = mode or learning.get("mode", "frag_mich")
    
    context_patterns = analyze_context_patterns(activities)
    sequence_patterns = analyze_sequence_patterns(activities)
    exceptions = analyze_exceptions(activities)
    all_suggestions = context_patterns + sequence_patterns + exceptions
    
    if not all_suggestions:
        return "🔍 Keine Muster gefunden. Mach weiter so – ich lerne dazu!"
    
    accepted = [a.get("suggestion", {}).get("suggestion", "") for a in learning.get("accepted", [])]
    rejected = [r.get("suggestion", {}).get("suggestion", "") for r in learning.get("rejected", [])]
    
    new_suggestions = []
    for s in all_suggestions:
        if s["suggestion"] not in accepted and s["suggestion"] not in rejected:
            new_suggestions.append(s)
    
    if not new_suggestions:
        return "🧠 Alle erkannten Muster sind schon gelernt."
    
    if current_mode == "mach_einfach" or learning.get("auto_mode", False):
        created = []
        for s in new_suggestions[:3]:
            if s["type"] != "ausnahme":
                result = create_routine_from_suggestion(s, username)
                created.append(f"• {s['suggestion']} → {result}")
                learning["accepted"].append({
                    "suggestion": s,
                    "timestamp": datetime.now().isoformat()
                })
        _save_learning(learning)
        return f"🤖 Auto-Mode aktiv! Routinen erstellt:\n\n" + "\n".join(created)
    
    if current_mode == "lern_still":
        learning["pending"] = new_suggestions[:5]
        _save_learning(learning)
        return f"📝 {len(new_suggestions[:5])} Muster gespeichert. Ich frage dich später."
    
    if current_mode == "erklaer_mir":
        ausgabe = "🧠 *Verhaltensanalyse (mit Erklärung):*\n\n"
        for i, s in enumerate(new_suggestions[:5], 1):
            ausgabe += f"{i}. {s['suggestion']}"
            if s.get("count"):
                ausgabe += f" ({s['count']}x)"
            if s.get("context"):
                ausgabe += f"\n   📌 Kontext: {s['context']}"
            if s.get("sequence"):
                ausgabe += f"\n   🔄 Sequenz: {s['sequence']}"
            ausgabe += "\n"
        ausgabe += f"\n💡 Ich habe {len(new_suggestions[:5])} Muster gefunden. Sag 'antwort ja' oder 'antwort nein'."
        return ausgabe
    
    # ─── MODUS: FRAG MICH (Standard) ───
    learning["pending"] = new_suggestions[:5]
    _save_learning(learning)
    
    ausgabe = "🧠 *Lernmodus – Neue Muster erkannt:*\n\n"
    for i, s in enumerate(new_suggestions[:5], 1):
        ausgabe += f"{i}. {s['suggestion']}"
        if s.get("count"):
            ausgabe += f" ({s['count']}x)"
        if s.get("context"):
            ausgabe += f"\n   📌 Kontext: {s['context']}"
        if s.get("sequence"):
            ausgabe += f"\n   🔄 Sequenz: {s['sequence']}"
        ausgabe += "\n"
    
    ausgabe += "\n💡 Sag 'antwort ja' oder 'antwort nein' (oder 'auto' für automatisch)."
    
    if new_suggestions:
        _push_learning_question(new_suggestions[0])
    
    return ausgabe

# ─── ROUTINE AUS VORSCHLAG ERSTELLEN ───
def create_routine_from_suggestion(suggestion, username=None):
    if username is None:
        username = _get_current_user()
    try:
        from plugins.routines_plugin import routine_hinzufuegen
        if suggestion["type"] == "kontext":
            name = suggestion["routine_name"]
            trigger = "sprache"
            trigger_wert = f"kontext {suggestion['context']}"
            wochentage = None
            aktionen = [suggestion["command"]]
        elif suggestion["type"] == "sequenz":
            name = suggestion["routine_name"]
            trigger = "sprache"
            trigger_wert = f"sequenz {name}"
            wochentage = None
            aktionen = suggestion["sequence"].split(" → ")
        elif suggestion["type"] == "zeit":
            name = suggestion["routine_name"]
            trigger = "zeit"
            trigger_wert = suggestion["hour"]
            wochentage = suggestion.get("weekdays", [])
            aktionen = [suggestion["command"]]
        else:
            return "Unbekannter Vorschlagstyp."
        result = routine_hinzufuegen(name, trigger, trigger_wert, aktionen, wochentage=wochentage, username=username)
        return f"✅ Routine '{name}' erstellt: {result}"
    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Routine: {e}")
        return f"❌ Fehler beim Erstellen der Routine: {e}"

# ─── PUSH FÜR LERNMODUS ───
def _push_learning_question(suggestion):
    try:
        from plugins.push_plugin import push_text
        msg = f"🧠 *Lernmodus – Neues Muster erkannt:*\n\n"
        msg += f"📊 {suggestion['suggestion']}"
        if suggestion.get("count"):
            msg += f" ({suggestion['count']}x)"
        if suggestion.get("context"):
            msg += f"\n📌 Kontext: {suggestion['context']}"
        if suggestion.get("sequence"):
            msg += f"\n🔄 Sequenz: {suggestion['sequence']}"
        msg += f"\n\n💡 Soll ich daraus eine Routine machen?\n"
        msg += f"→ 'antwort ja' oder 'antwort nein' (oder 'antwort auto')"
        push_text(msg)
        return True
    except Exception as e:
        logging.error(f"Push-Fehler: {e}")
        return False

# ─── LERNMODUS-ANTWORTEN ───
def handle_learning_response(response, username=None):
    if username is None:
        username = _get_current_user()
    learning = _load_learning()
    pending = learning.get("pending", [])
    if not pending:
        return "🤔 Keine offenen Vorschläge zum Lernen."
    suggestion = pending[0]
    
    if response in ("ja", "yes", "ok", "mach"):
        result = create_routine_from_suggestion(suggestion, username)
        learning["accepted"].append({
            "suggestion": suggestion,
            "timestamp": datetime.now().isoformat()
        })
        send_notification("Pia Lernmodus", f"✅ Vorschlag angenommen: {suggestion['suggestion']}")
    elif response in ("nein", "no", "nicht", "lass"):
        learning["rejected"].append({
            "suggestion": suggestion,
            "timestamp": datetime.now().isoformat()
        })
        send_notification("Pia Lernmodus", f"❌ Vorschlag abgelehnt: {suggestion['suggestion']}")
        result = "❌ Vorschlag abgelehnt."
    elif response in ("auto", "automatisch"):
        learning["auto_mode"] = True
        result = create_routine_from_suggestion(suggestion, username)
        learning["accepted"].append({
            "suggestion": suggestion,
            "timestamp": datetime.now().isoformat()
        })
        send_notification("Pia Lernmodus", f"🤖 Auto-Modus aktiviert! Routine erstellt: {suggestion['suggestion']}")
    else:
        return "❌ Unbekannte Antwort. Sag 'antwort ja', 'antwort nein' oder 'antwort auto'."
    
    learning["pending"] = learning["pending"][1:]
    _save_learning(learning)
    
    if learning["pending"]:
        next_suggestion = learning["pending"][0]
        _push_learning_question(next_suggestion)
        return f"{result}\n\n📌 Nächster Vorschlag: {next_suggestion['suggestion']}"
    return f"{result}\n\n✅ Lernmodus abgeschlossen. Keine offenen Vorschläge mehr."

# ─── AGENTIC-MODUS-FUNKTIONEN (integriert) ───
def set_learning_mode(mode):
    valid_modes = ["frag_mich", "mach_einfach", "erklaer_mir", "lern_still"]
    if mode not in valid_modes:
        return f"❌ Ungültiger Modus. Verfügbar: {', '.join(valid_modes)}"
    learning = _load_learning()
    learning["mode"] = mode
    _save_learning(learning)
    return f"🧠 Lernmodus auf '{mode}' gesetzt."

def get_learning_status():
    learning = _load_learning()
    return f"""🧠 *Lernmodus-Status:*
• Modus: {learning.get('mode', 'frag_mich')}
• Angenommen: {len(learning.get('accepted', []))}
• Abgelehnt: {len(learning.get('rejected', []))}
• Offene Vorschläge: {len(learning.get('pending', []))}
• Auto-Mode: {'✅' if learning.get('auto_mode', False) else '❌'}"""

def reset_learning():
    _save_learning({"accepted": [], "rejected": [], "mode": "frag_mich", "auto_mode": False})
    return "🗑️ Lernmodus zurückgesetzt."

def get_learning_explanation():
    learning = _load_learning()
    mode = learning.get("mode", "frag_mich")
    return f"""🧠 *Lernmodus-Erklärung:*

Ich bin der Lernmodus von Pia. Ich speichere, was du magst und was nicht.

**Modi:**
• **frag_mich** – Ich frage immer nach (Standard).
• **mach_einfach** – Ich führe Vorschläge automatisch aus.
• **erklaer_mir** – Ich erkläre, warum ich etwas vorschlage.
• **lern_still** – Ich speichere Muster, ohne zu fragen oder auszuführen.

**Aktueller Modus:** {mode}

Sag 'modus <mode>' um zu wechseln.
"""

# ─── HAUPTBEFEHLE ───
def handle_behavior(befehl):
    clean = befehl.lower().strip()
    username = _get_current_user()
    
    # ─── LERNMODUS-ANTWORTEN ───
    if clean in ("ja", "yes", "ok", "mach", "nein", "no", "nicht", "lass", "auto", "automatisch"):
        return handle_learning_response(clean, username)
    
    # ─── ANALYSE ───
    if any(w in clean for w in ["analysiere", "muster", "verhalten", "kontext", "sequenz", "ausnahme"]):
        return analyze_behavior(username)
    
    # ─── MODUS WECHSELN ───
    if "modus" in clean:
        for mode in ["frag_mich", "mach_einfach", "erklaer_mir", "lern_still"]:
            if mode in clean:
                return set_learning_mode(mode)
        return f"Verfügbare Modi: frag_mich, mach_einfach, erklaer_mir, lern_still"
    
    # ─── STATUS ───
    if "status" in clean or "statistik" in clean or "stats" in clean:
        return get_learning_status()
    
    # ─── RESET ───
    if "reset" in clean:
        return reset_learning()
    
    # ─── ERKLÄRUNG ───
    if "erklärung" in clean or "erkläre" in clean:
        return get_learning_explanation()
    
    return """🧠 *Verhaltensanalyse + Lernmodus:*

• 'analysiere' – Muster erkennen (Kontext, Sequenzen, Ausnahmen)
• 'modus <mode>' – Lernmodus wechseln (frag_mich, mach_einfach, erklaer_mir, lern_still)
• 'status' / 'statistik' – Aktuellen Status anzeigen
• 'reset' – Zurücksetzen
• 'erklärung' – Erklärung anzeigen
• 'antwort ja/nein/auto' – Auf Vorschläge reagieren"""

# ─── TOOLS ───
def tools_holen():
    return [
        ("analyze_behavior", analyze_behavior, "Verhaltensanalyse"),
        ("analyze_context_patterns", analyze_context_patterns, "Kontext-Muster"),
        ("analyze_sequence_patterns", analyze_sequence_patterns, "Sequenz-Muster"),
        ("analyze_exceptions", analyze_exceptions, "Ausnahmen"),
        ("log_context", log_context, "Kontext loggen"),
        ("create_routine_from_suggestion", create_routine_from_suggestion, "Routine erstellen"),
        ("handle_learning_response", handle_learning_response, "Lernmodus"),
        ("set_learning_mode", set_learning_mode, "Lernmodus setzen"),
        ("get_learning_status", get_learning_status, "Lernmodus-Status"),
        ("reset_learning", reset_learning, "Lernmodus zurücksetzen"),
    ]