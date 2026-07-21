# plugins/agentic_plugin.py – Agentic 2.0 (Lernmodus mit mehr Modi)

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from utils import lade_json, speichere_json, logging, sprich

def register(core):
    core.register_command(
        ["agentic", "lernmodus", "modus", "feedback", "lerne"],
        handle_agentic,
        "Agentic 2.0 – Lernmodus mit mehr Modi"
    )

# ─── KONFIG ───
FEEDBACK_FILE = "agentic_feedback.json"

def _load_feedback():
    return lade_json(FEEDBACK_FILE, {
        "accepted": [],
        "rejected": [],
        "mode": "frag_mich",
        "auto_mode": False
    })

def _save_feedback(data):
    speichere_json(FEEDBACK_FILE, data)

# ─── HAUPTFUNKTION ───
def handle_agentic(befehl):
    clean = befehl.lower().strip()
    username = "jan"  # Immer Jan für agentic (oder aus active_user lesen)
    
    # ─── MODUS WECHSELN ───
    if "modus" in clean:
        modes = ["frag_mich", "mach_einfach", "erklaer_mir", "lern_still"]
        for mode in modes:
            if mode in clean:
                data = _load_feedback()
                data["mode"] = mode
                _save_feedback(data)
                return f"🧠 Lernmodus auf '{mode}' gesetzt."
        return f"Verfügbare Modi: {', '.join(modes)}"
    
    # ─── STATUS ───
    if "status" in clean:
        data = _load_feedback()
        return f"""🧠 *Agentic-Status:*
• Modus: {data.get('mode', 'frag_mich')}
• Angenommen: {len(data.get('accepted', []))}
• Abgelehnt: {len(data.get('rejected', []))}
• Auto-Mode: {'✅' if data.get('auto_mode', False) else '❌'}"""
    
    # ─── STATISTIK ───
    if "statistik" in clean or "stats" in clean:
        data = _load_feedback()
        return f"""📊 *Agentic-Statistik:*
• Angenommen: {len(data.get('accepted', []))}
• Abgelehnt: {len(data.get('rejected', []))}
• Auto-Mode: {'✅ aktiv' if data.get('auto_mode', False) else '❌ inaktiv'}
• Modus: {data.get('mode', 'frag_mich')}"""
    
    # ─── RESET ───
    if "reset" in clean:
        _save_feedback({"accepted": [], "rejected": [], "mode": "frag_mich", "auto_mode": False})
        return "🗑️ Agentic zurückgesetzt."
    
    # ─── ERKLÄRUNG ───
    if "erklärung" in clean or "erkläre" in clean:
        data = _load_feedback()
        mode = data.get("mode", "frag_mich")
        return f"""🧠 *Agentic-Erklärung:*

Ich bin der Lernmodus von Pia. Ich speichere, was du magst und was nicht.

**Modi:**
• **frag_mich** – Ich frage immer nach (Standard).
• **mach_einfach** – Ich führe Vorschläge automatisch aus.
• **erklaer_mir** – Ich erkläre, warum ich etwas vorschlage.
• **lern_still** – Ich speichere Muster, ohne zu fragen oder auszuführen.

**Aktueller Modus:** {mode}

Sag 'modus <mode>' um zu wechseln.
"""
    
    # ─── HILFE ───
    return """🧠 *Agentic 2.0 – Lernmodus:*

• 'modus <mode>' – Lernmodus wechseln (frag_mich, mach_einfach, erklaer_mir, lern_still)
• 'status' – Aktuellen Status anzeigen
• 'statistik' / 'stats' – Statistiken anzeigen
• 'reset' – Zurücksetzen
• 'erklärung' / 'erkläre' – Erklärung anzeigen

💡 Pia lernt aus deinem Feedback und passt sich an!
"""

# ─── TOOLS ───
def tools_holen():
    return [
        ("handle_agentic", handle_agentic, "Agentic 2.0"),
        ("_load_feedback", _load_feedback, "Feedback laden"),
        ("_save_feedback", _save_feedback, "Feedback speichern"),
    ]