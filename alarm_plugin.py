# plugins/alarm_plugin.py – Timer & Alarm (Browser-Sprache + Lautsprecher)

import threading
import time
import re
from datetime import datetime, timedelta
from utils import sprich, send_notification, logging

def register(core):
    core.register_command(
        ["alarm", "timer", "wecker", "erinnere mich"],
        handle_alarm,
        "Alarm/Timer setzen"
    )

# ─── AKTIVE TIMER ───
_timer_threads = []

def timer_setzen(sekunden, nachricht="Timer abgelaufen", wiederholung=1):
    """Setzt einen Timer für X Sekunden."""
    def timer_abgelaufen():
        for i in range(wiederholung):
            sprich(nachricht)
            send_notification("Timer", nachricht)
            time.sleep(2)
        logging.info(f"[Timer] Abgelaufen: {nachricht}")
    
    t = threading.Timer(sekunden, timer_abgelaufen)
    t.daemon = True
    t.start()
    _timer_threads.append(t)
    
    minuten = sekunden // 60
    rest_sekunden = sekunden % 60
    zeit_str = f"{minuten} Minute(n) und {rest_sekunden} Sekunden" if minuten > 0 else f"{sekunden} Sekunden"
    return f"⏰ Timer für {zeit_str} gestartet: {nachricht}"

def alarm_setzen(uhrzeit, nachricht="Alarm!"):
    """Setzt einen Alarm zu einer bestimmten Uhrzeit (z.B. 06:30)."""
    try:
        if ":" in uhrzeit:
            stunden, minuten = map(int, uhrzeit.split(":"))
        else:
            stunden = int(uhrzeit)
            minuten = 0
        
        jetzt = datetime.now()
        ziel = jetzt.replace(hour=stunden, minute=minuten, second=0, microsecond=0)
        
        if ziel <= jetzt:
            ziel += timedelta(days=1)
        
        sekunden_bis = (ziel - jetzt).total_seconds()
        
        def alarm_ausloesen():
            for i in range(3):
                sprich(f"{nachricht}! Aufwachen!")
                send_notification("Alarm", nachricht)
                time.sleep(2)
            sprich(f"Guten Morgen! Es ist {ziel.strftime('%H:%M')} Uhr.")
        
        t = threading.Timer(sekunden_bis, alarm_ausloesen)
        t.daemon = True
        t.start()
        _timer_threads.append(t)
        
        return f"⏰ Alarm für {ziel.strftime('%H:%M')} Uhr gesetzt: {nachricht}"
        
    except Exception as e:
        return f"❌ Fehler beim Setzen des Alarms: {e}"

def timer_abbrechen():
    """Bricht alle Timer ab."""
    global _timer_threads
    count = 0
    for t in _timer_threads:
        if t.is_alive():
            t.cancel()
            count += 1
    _timer_threads.clear()
    return f"🛑 {count} Timer abgebrochen."

def handle_alarm(befehl):
    clean = befehl.lower().strip()
    
    # ─── ALLE TIMER ABBRECHEN ───
    if any(w in clean for w in ["abbrechen", "stopp", "cancel"]):
        return timer_abbrechen()
    
    # ─── ALARM: "Alarm um 06:30" ───
    match = re.search(r'(?:alarm|wecker)\s+um\s+(\d{1,2}:\d{2})', clean)
    if match:
        uhrzeit = match.group(1)
        # Nachricht extrahieren
        nachricht = re.sub(r'(?:alarm|wecker)\s+um\s+\d{1,2}:\d{2}\s+', '', befehl).strip()
        if not nachricht:
            nachricht = "Aufwachen!"
        return alarm_setzen(uhrzeit, nachricht)
    
    # ─── ALARM: "Alarm um 6" ───
    match = re.search(r'(?:alarm|wecker)\s+um\s+(\d{1,2})(?:\s+uhr)?', clean)
    if match:
        uhrzeit = f"{int(match.group(1)):02d}:00"
        nachricht = re.sub(r'(?:alarm|wecker)\s+um\s+\d{1,2}(?:\s+uhr)?\s+', '', befehl).strip()
        if not nachricht:
            nachricht = "Aufwachen!"
        return alarm_setzen(uhrzeit, nachricht)
    
    # ─── TIMER: "Timer 5 Minuten" ───
    match = re.search(r'timer\s+(\d+)\s*(?:minuten?|min|m)', clean)
    if match:
        minuten = int(match.group(1))
        nachricht = re.sub(r'timer\s+\d+\s*(?:minuten?|min|m)\s+', '', befehl).strip()
        if not nachricht:
            nachricht = f"Timer {minuten} Minuten abgelaufen."
        return timer_setzen(minuten * 60, nachricht)
    
    # ─── TIMER: "Timer 30 Sekunden" ───
    match = re.search(r'timer\s+(\d+)\s*(?:sekunden?|s)', clean)
    if match:
        sekunden = int(match.group(1))
        nachricht = re.sub(r'timer\s+\d+\s*(?:sekunden?|s)\s+', '', befehl).strip()
        if not nachricht:
            nachricht = f"Timer {sekunden} Sekunden abgelaufen."
        return timer_setzen(sekunden, nachricht)
    
    # ─── ERINNERUNG: "erinnere mich in 5 Minuten an Müll" ───
    match = re.search(r'erinnere mich in (\d+)\s*(?:minuten?|min|m)\s+an\s+(.+)', clean)
    if match:
        minuten = int(match.group(1))
        nachricht = match.group(2).strip()
        return timer_setzen(minuten * 60, f"Erinnerung: {nachricht}", wiederholung=2)
    
    match = re.search(r'erinnere mich in (\d+)\s*(?:sekunden?|s)\s+an\s+(.+)', clean)
    if match:
        sekunden = int(match.group(1))
        nachricht = match.group(2).strip()
        return timer_setzen(sekunden, f"Erinnerung: {nachricht}", wiederholung=2)
    
    return """⏰ Alarm/Timer-Befehle:
• 'alarm um 06:30' – Wecker stellen
• 'alarm um 7' – Wecker um 7:00 Uhr
• 'timer 5 Minuten' – Timer für 5 Minuten
• 'timer 30 Sekunden' – Timer für 30 Sekunden
• 'erinnere mich in 10 Minuten an Müll' – Erinnerung
• 'timer abbrechen' – Alle Timer stoppen"""

def tools_holen():
    return [
        ("timer_setzen", timer_setzen, "Timer"),
        ("alarm_setzen", alarm_setzen, "Alarm"),
        ("timer_abbrechen", timer_abbrechen, "Timer abbrechen"),
    ]