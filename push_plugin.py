# plugins/push_plugin.py – Push-Benachrichtigungen (Telegram)
# Pushes: Termine (Änderung + geplant), Wetter (Änderung + geplant), Routinen (Ausführung)
# Einkaufsliste nur auf Nachfrage

import threading
import time
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from utils import lade_json, KONFIG, logging, send_notification, BASE_DIR

def register(core):
    core.register_command(
        ["push", "erinnerung", "tägliche zusammenfassung", "wetter push", "einkauf"],
        handle_push,
        "Push-Benachrichtigungen (Telegram)"
    )

# ─── TELEGRAM ───
def _send_telegram(text):
    token = KONFIG.get("telegram_bot_token")
    chat_id = KONFIG.get("telegram_chat_id")
    if not token or not chat_id:
        logging.warning("Telegram nicht konfiguriert.")
        return False
    try:
        import requests
        import re
        text_escaped = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text_escaped, "parse_mode": "MarkdownV2"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Telegram Fehler: {e}")
        return False

# ─── HAUPT-PUSH-FUNKTION (für andere Plugins) ───
def push_text(text):
    """Sendet eine Push-Nachricht (Telegram + lokal). Wird von anderen Plugins genutzt."""
    send_notification("Pia", text)
    _send_telegram(text)
    return True

# ─── TERMIN-HELPER (für geplante Pushes) ───
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

def _get_appointment_details(username=None):
    if username is None:
        username = _get_current_user()
    try:
        file = f"kalender_{username}.json"
        daten = lade_json(file, {"termine": []})
        heute = datetime.now().strftime("%Y-%m-%d")
        zukunft = [t for t in daten.get("termine", []) 
                   if t.get("datum") >= heute and t.get("status") != "erledigt"]
        if not zukunft:
            return None
        zukunft.sort(key=lambda x: (x.get("datum", "9999-99-99"), x.get("uhrzeit", "99:99")))
        return zukunft[0]
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Termindetails: {e}")
        return None

def _get_today_appointments(username=None):
    if username is None:
        username = _get_current_user()
    try:
        from plugins.calendar_plugin import termine_heute
        return termine_heute(username=username)
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der heutigen Termine: {e}")
        return None

def _is_vortag(termin_datum):
    heute = datetime.now().date()
    try:
        termin = datetime.strptime(termin_datum, "%Y-%m-%d").date()
        return (termin - heute).days == 1
    except:
        return False

def _is_termin_tag(termin_datum):
    heute = datetime.now().date()
    try:
        termin = datetime.strptime(termin_datum, "%Y-%m-%d").date()
        return termin == heute
    except:
        return False

def _get_weather():
    try:
        from plugins.weather_plugin import wetter_holen
        return wetter_holen("Eschwege")
    except Exception as e:
        logging.error(f"Fehler beim Abrufen des Wetters: {e}")
        return None

def _get_proactive_suggestions():
    try:
        from plugins.proactive_plugin import get_all_suggestions
        return get_all_suggestions()
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Vorschläge: {e}")
        return None

def _get_shopping_items(username=None):
    if username is None:
        username = _get_current_user()
    try:
        from plugins.shopping_plugin import einkaufsliste_anzeigen
        return einkaufsliste_anzeigen(username=username)
    except Exception as e:
        logging.error(f"Fehler beim Abrufen der Einkaufsliste: {e}")
        return None

# ─── PUSH-FUNKTIONEN (manuell) ───
def push_reminder():
    """Termin-Erinnerung manuell auslösen."""
    username = _get_current_user()
    termin = _get_appointment_details(username)
    if not termin:
        return "Keine anstehenden Termine."
    
    titel = termin.get("titel", "Termin")
    uhrzeit = termin.get("uhrzeit", "??:??")
    datum = termin.get("datum", "??")
    
    if _is_vortag(datum):
        msg = f"🔔 Morgen hast du *{titel}* um *{uhrzeit}* Uhr."
    elif _is_termin_tag(datum):
        msg = f"🔔 Heute um *{uhrzeit}* Uhr: *{titel}*!"
    else:
        msg = f"📅 Nächster Termin: *{titel}* am {datum} um {uhrzeit} Uhr."
    
    push_text(msg)
    return msg

def push_weather():
    """Wetter-Push (manuell)."""
    wetter = _get_weather()
    if wetter:
        push_text(f"☀️ *Wetter heute:* {wetter}")
        return wetter
    return "Wetter nicht verfügbar."

def push_shopping():
    """Einkaufsliste-Push (manuell)."""
    username = _get_current_user()
    items = _get_shopping_items(username)
    if items and "leer" not in items.lower():
        push_text(f"🛒 *Einkaufsliste:* {items}")
        return items
    return "Einkaufsliste ist leer."

def push_daily_summary():
    """Tägliche Zusammenfassung (Wetter + Termine)."""
    username = _get_current_user()
    wetter = _get_weather() or "Wetter nicht verfügbar."
    termine = _get_today_appointments(username) or "Keine Termine heute."
    
    msg = f"📅 *Guten Morgen {username}!*\n\n"
    msg += f"☀️ *Wetter:* {wetter}\n\n"
    msg += f"📋 *Heute:*\n{termine}"
    
    push_text(msg)
    return msg

def push_proactive():
    """Proaktive Vorschläge pushen."""
    suggestions = _get_proactive_suggestions()
    if suggestions:
        msg = "💡 *Proaktive Vorschläge:*\n\n"
        for s in suggestions[:3]:
            msg += f"• {s.get('title', 'Vorschlag')}\n"
            msg += f"  {s.get('description', '')}\n\n"
        push_text(msg.strip())
        return msg
    return "Keine neuen Vorschläge."

# ─── HAUPTBEFEHLE ───
def handle_push(befehl):
    clean = befehl.lower().strip()
    
    # ─── TERMIN-ERINNERUNG ───
    if "erinnerung" in clean or "reminder" in clean:
        return push_reminder()
    
    # ─── WETTER ───
    if "wetter" in clean:
        return push_weather()
    
    # ─── EINKAUFSLISTE ───
    if "einkauf" in clean or "shopping" in clean:
        return push_shopping()
    
    # ─── TÄGLICHE ZUSAMMENFASSUNG ───
    if "tägliche zusammenfassung" in clean or "daily summary" in clean or "übersicht" in clean:
        return push_daily_summary()
    
    # ─── PROAKTIVE VORSCHLÄGE ───
    if "proaktiv" in clean or "vorschlag" in clean:
        return push_proactive()
    
    # ─── TEST ───
    if "test" in clean:
        return push_text("🔔 Test-Push von Pia!")
    
    # ─── HILFE ───
    return """Push-Befehle:
• 'erinnerung' – Nächsten Termin erinnern
• 'wetter' – Wetter pushen
• 'einkauf' – Einkaufsliste anzeigen
• 'tägliche zusammenfassung' – Tägliche Übersicht
• 'proaktiv' – Proaktive Vorschläge
• 'test' – Test-Push"""

# ─── SCHEDULER (automatische Pushes) ───
_scheduler_running = False
_scheduler_thread = None
_last_reminder = {}
_last_daily_date = None
_last_proactive_date = None
_last_weather = None

def _push_weather_change(neues_wetter):
    """Push bei Wetter-Änderungen (nur bei +-5°C oder Regen/Schnee)."""
    global _last_weather
    try:
        if _last_weather is None:
            push_text(f"☀️ *Wetter heute:* {neues_wetter}")
            _last_weather = neues_wetter
            return
        
        temp_match = re.search(r'([-+]?\d+\.?\d*)\s*°C', neues_wetter)
        old_temp_match = re.search(r'([-+]?\d+\.?\d*)\s*°C', _last_weather)
        
        if temp_match and old_temp_match:
            new_temp = float(temp_match.group(1))
            old_temp = float(old_temp_match.group(1))
            if abs(new_temp - old_temp) > 5:
                push_text(f"🌡️ *Wetter ändert sich:* {neues_wetter}")
                _last_weather = neues_wetter
                return
        
        wetter_terms = ["regen", "schnee", "gewitter", "sturm", "hagel"]
        if any(w in neues_wetter.lower() for w in wetter_terms):
            if not any(w in _last_weather.lower() for w in wetter_terms):
                push_text(f"🌧️ *Wetterwarnung:* {neues_wetter}")
                _last_weather = neues_wetter
                return
        
        _last_weather = neues_wetter
        
    except Exception as e:
        logging.error(f"Push-Fehler (Wetteränderung): {e}")

def _scheduler_loop():
    global _scheduler_running, _last_reminder, _last_daily_date, _last_proactive_date
    
    while _scheduler_running:
        try:
            now = datetime.now()
            stunde = now.hour
            minute = now.minute
            heute = now.date()
            username = _get_current_user()
            
            # ─── 1. TERMIN-ERINNERUNG (Vortag 3x, Termintag 1x) ───
            if (stunde == 7 and minute == 30) or \
               (stunde == 12 and minute == 30) or \
               (stunde == 19 and minute == 30):
                
                termin = _get_appointment_details(username)
                if termin:
                    termin_datum = termin.get("datum")
                    termin_titel = termin.get("titel", "Termin")
                    termin_uhrzeit = termin.get("uhrzeit", "??:??")
                    termin_id = termin.get("id")
                    
                    if _is_vortag(termin_datum):
                        key = f"{username}_{termin_id}_vortag"
                        if _last_reminder.get(key) != heute:
                            msg = f"🔔 Morgen hast du *{termin_titel}* um *{termin_uhrzeit}* Uhr."
                            push_text(msg)
                            _last_reminder[key] = heute
                            logging.info(f"[Push] Vortag-Erinnerung: {termin_titel}")
                    
                    elif _is_termin_tag(termin_datum) and stunde == 7:
                        key = f"{username}_{termin_id}_tag"
                        if _last_reminder.get(key) != True:
                            msg = f"🔔 Heute um *{termin_uhrzeit}* Uhr: *{termin_titel}*!"
                            push_text(msg)
                            _last_reminder[key] = True
                            logging.info(f"[Push] Termin-Tag Erinnerung: {termin_titel}")
            
            # ─── 2. TÄGLICHES WETTER (07:00 Uhr) ───
            if stunde == 7 and minute == 0:
                if _last_daily_date != heute:
                    wetter = _get_weather()
                    if wetter:
                        push_text(f"☀️ *Wetter heute:* {wetter}")
                        _last_daily_date = heute
                        logging.info("[Push] Tägliches Wetter gesendet")
            
            # ─── 3. PROAKTIVE VORSCHLÄGE (08:00 Uhr) ───
            if stunde == 8 and minute == 0:
                if _last_proactive_date != heute:
                    suggestions = _get_proactive_suggestions()
                    if suggestions:
                        msg = "💡 *Proaktive Vorschläge:*\n\n"
                        for s in suggestions[:3]:
                            msg += f"• {s.get('title', 'Vorschlag')}\n"
                            msg += f"  {s.get('description', '')}\n\n"
                        push_text(msg.strip())
                        _last_proactive_date = heute
                        logging.info("[Push] Proaktive Vorschläge gesendet")
            
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"Push-Scheduler Fehler: {e}")
            time.sleep(60)

def start_push_scheduler():
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return "Push-Scheduler läuft bereits."
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logging.info("Push-Scheduler gestartet")
    return "Push-Scheduler gestartet."

def stop_push_scheduler():
    global _scheduler_running
    if not _scheduler_running:
        return "Push-Scheduler läuft nicht."
    _scheduler_running = False
    logging.info("Push-Scheduler gestoppt")
    return "Push-Scheduler gestoppt."

# ─── TOOLS ───
def tools_holen():
    return [
        ("push_text", push_text, "Push senden"),
        ("push_reminder", push_reminder, "Termin-Erinnerung"),
        ("push_weather", push_weather, "Wetter-Push"),
        ("push_shopping", push_shopping, "Einkaufsliste"),
        ("push_daily_summary", push_daily_summary, "Tägliche Zusammenfassung"),
        ("push_proactive", push_proactive, "Proaktive Vorschläge"),
        ("start_push_scheduler", start_push_scheduler, "Push-Scheduler starten"),
        ("stop_push_scheduler", stop_push_scheduler, "Push-Scheduler stoppen"),
    ]