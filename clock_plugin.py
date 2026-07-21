# plugins/clock_plugin.py – Uhrzeit, Datum, Wochentag

from datetime import datetime

def register(core):
    core.register_command(["wie spät", "uhrzeit", "zeit", "datum", "wochentag", "tag ist heute"], handle_clock, "Uhrzeit & Datum")

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

def jetzt_sagen(was="alles"):
    jetzt = datetime.now()
    if was.lower() in ("uhrzeit", "zeit", "jetzt"):
        text = jetzt.strftime("%H:%M Uhr")
    elif was.lower() in ("datum", "heute"):
        text = jetzt.strftime("%d. %B %Y")
    elif was.lower() in ("tag", "wochentag"):
        text = WOCHENTAGE[jetzt.weekday()]
    else:
        text = jetzt.strftime("%H:%M Uhr am %d. %B %Y – %A")
    return text

def handle_clock(befehl):
    """Verarbeitet Uhrzeit/Datum-Befehle."""
    clean = befehl.lower().strip()
    if "datum" in clean or "tag ist heute" in clean:
        return jetzt_sagen("datum")
    else:
        return jetzt_sagen("uhrzeit")