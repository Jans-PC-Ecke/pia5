#!/usr/bin/env python3
# webui.py – Pia5 WebUI (mit Shopping-ID/Name-Fix)

import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, send_file, Response

# ─── PFADE ───
BASE_DIR = Path(__file__).parent.resolve()
PLUGIN_DIR = BASE_DIR / "plugins"
sys.path.insert(0, str(PLUGIN_DIR))

# ─── KERN ───
from assistant_core import befehl_verarbeiten, authenticate_with_pin
from user_profiles import logout as user_logout
from utils import KONFIG, lade_json, sprich_zu_datei

# ─── PLUGINS IMPORTIEREN ───
try:
    from plugins.routines_plugin import (
        starte_scheduler, stoppe_scheduler, _scheduler_running,
        routinen_alle, _lade_routinen,
        routine_ausfuehren, routine_toggle, routine_loeschen, routine_aktualisieren
    )
except ImportError:
    starte_scheduler = stoppe_scheduler = None
    _scheduler_running = False
    routinen_alle = _lade_routinen = routine_ausfuehren = routine_toggle = routine_loeschen = routine_aktualisieren = None

try:
    from plugins.tapo_plugin import tapo_steuern, tapo_status
except ImportError:
    tapo_steuern = tapo_status = None

try:
    from plugins.calendar_plugin import (
        termine_heute, termine_monat, termin_hinzufuegen,
        termin_erledigen, termin_loeschen
    )
except ImportError:
    termine_heute = termine_monat = termin_hinzufuegen = termin_erledigen = termin_loeschen = None

try:
    from plugins.shopping_plugin import (
        einkaufsliste_anzeigen,
        einkaufsliste_hinzufuegen,
        einkaufsliste_entfernen,
        einkaufsliste_erledigt,
        einkaufsliste_leeren
    )
except ImportError:
    einkaufsliste_anzeigen = None
    einkaufsliste_hinzufuegen = None
    einkaufsliste_entfernen = None
    einkaufsliste_erledigt = None
    einkaufsliste_leeren = None

try:
    from plugins.memory_plugin import get_facts
except ImportError:
    get_facts = None

try:
    from plugins.proactive_plugin import get_suggestions, accept_suggestion, reject_suggestion, trigger_analysis
except ImportError:
    get_suggestions = accept_suggestion = reject_suggestion = trigger_analysis = None

try:
    from plugins.push_plugin import start_push_scheduler
except ImportError:
    start_push_scheduler = None

# ─── FLASK ───
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# ─── SESSION SYNC ───
def sync_session_with_user():
    try:
        active_file = Path("active_user.json")
        if active_file.exists():
            with open(active_file, "r") as f:
                data = json.load(f)
            username = data.get("username", "jan")
            session['username'] = username
            return username
    except Exception as e:
        logging.error(f"Session Sync Fehler: {e}")
    return None

# ─── AUTH-CHECK ───
@app.before_request
def check_auth():
    if request.endpoint in ['static', 'login', 'api_auth', 'api_unauthorized', 'api_tts', 'api_events']:
        return
    sync_session_with_user()
    if not session.get('authorized', False):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Autorisierung erforderlich', 'auth_required': True}), 401
        return redirect(url_for('login'))

# ─── ROUTES ───
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pin = request.form.get('pin', '')
        success, username = authenticate_with_pin(pin)
        if success:
            session['authorized'] = True
            session['username'] = username
            sync_session_with_user()
            return redirect(url_for('index'))
        return render_template('login.html', error='❌ Falsche PIN')
    return render_template('login.html')

@app.route('/logout')
def logout():
    user_logout()
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('authorized', False):
        return redirect(url_for('login'))
    current_user = sync_session_with_user()
    return render_template('index_simple.html', current_user=current_user)

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# ─── API: TTS ───
@app.route('/api/tts', methods=['POST'])
def api_tts():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'Kein Text'}), 400
    try:
        audio_file = sprich_zu_datei(text)
        if audio_file and audio_file.exists():
            return send_file(audio_file, mimetype='audio/mpeg', as_attachment=False)
        return jsonify({'error': 'Audio-Erzeugung fehlgeschlagen'}), 500
    except Exception as e:
        logging.error(f"TTS Fehler: {e}")
        return jsonify({'error': str(e)}), 500

# ─── API: AUTH ───
@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.get_json()
    pin = data.get('pin', '')
    success, username = authenticate_with_pin(pin)
    if success:
        session['authorized'] = True
        session['username'] = username
        sync_session_with_user()
        return jsonify({'success': True, 'message': f'Angemeldet als {username}', 'user': username})
    return jsonify({'success': False, 'message': 'Falsche PIN'}), 401

@app.route('/api/unauthorized', methods=['POST'])
def api_unauthorized():
    session.clear()
    return jsonify({'success': True, 'message': 'Abgemeldet'})

# ─── API: USER ───
@app.route('/api/user/current', methods=['GET'])
def api_user_current():
    try:
        active_file = Path("active_user.json")
        if active_file.exists():
            with open(active_file, "r") as f:
                data = json.load(f)
            username = data.get("username", "jan")
            return jsonify({'username': username})
    except:
        pass
    return jsonify({'username': 'jan'})

# ─── API: BEFEHLE ───
@app.route('/api/command', methods=['POST'])
def api_command():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    data = request.get_json()
    befehl = data.get('befehl', '')
    if not befehl:
        return jsonify({'error': 'Kein Befehl'}), 400
    antwort = befehl_verarbeiten(befehl)
    return jsonify({'antwort': antwort, 'user': session.get('username', 'jan')})

@app.route('/api/speech', methods=['POST'])
def api_speech():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Kein Text erkannt'}), 400
    antwort = befehl_verarbeiten(text)
    return jsonify({'antwort': antwort, 'user': session.get('username', 'jan')})

# ─── API: TAPO ───
@app.route('/api/tapo/status', methods=['GET'])
def api_tapo_status():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if tapo_status:
        try:
            status = tapo_status()
            return jsonify({'status': status})
        except Exception as e:
            logging.error(f"Tapo Status Fehler: {e}")
    return jsonify({'status': {}})

@app.route('/api/tapo/<device>/<action>', methods=['POST'])
def api_tapo(device, action):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if tapo_steuern:
        try:
            cmd = f'{device} an' if action in ('on', 'an') else f'{device} aus'
            antwort = tapo_steuern(cmd)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Tapo Fehler: {e}")
    return jsonify({'error': 'Tapo nicht verfügbar'}), 503

@app.route('/api/tapo/licht/rgb', methods=['POST'])
def api_rgb():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if tapo_steuern:
        try:
            data = request.get_json()
            r = data.get('r', 0)
            g = data.get('g', 0)
            b = data.get('b', 0)
            antwort = tapo_steuern(f'rgb {r} {g} {b}')
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"RGB Fehler: {e}")
    return jsonify({'error': 'Tapo nicht verfügbar'}), 503

@app.route('/api/tapo/licht/brightness/<int:value>', methods=['POST'])
def api_brightness(value):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if tapo_steuern:
        try:
            antwort = tapo_steuern(f'helligkeit {value}')
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Brightness Fehler: {e}")
    return jsonify({'error': 'Tapo nicht verfügbar'}), 503

# ─── API: KALENDER ───
@app.route('/api/calendar/today', methods=['GET'])
def api_calendar_today():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if termine_heute:
        try:
            result = termine_heute()
            return jsonify({'termine': result})
        except Exception as e:
            logging.error(f"Calendar Fehler: {e}")
    return jsonify({'termine': 'Fehler beim Laden'})

@app.route('/api/calendar/month/<int:year>/<int:month>', methods=['GET'])
def api_calendar_month(year, month):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if termine_monat:
        try:
            result = termine_monat(year, month)
            formatted = []
            for t in result:
                typ = "Erinnerung" if t.get("typ") == "erinnerung" else "Termin"
                formatted.append({
                    "id": t.get("id"),
                    "typ": typ,
                    "datum": t.get("datum"),
                    "uhrzeit": t.get("uhrzeit", "??:??"),
                    "titel": t.get("titel", "?"),
                    "ort": t.get("ort", ""),
                    "erledigt": t.get("status") == "erledigt"
                })
            return jsonify({'termine': formatted})
        except Exception as e:
            logging.error(f"Calendar Month Fehler: {e}")
    return jsonify({'termine': []})

@app.route('/api/calendar/add', methods=['POST'])
def api_calendar_add():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if termin_hinzufuegen:
        try:
            data = request.get_json()
            titel = data.get('titel', '')
            datum = data.get('datum', '')
            uhrzeit = data.get('uhrzeit', '08:00')
            ort = data.get('ort', '')
            antwort = termin_hinzufuegen(titel, datum, uhrzeit, ort)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Calendar Add Fehler: {e}")
    return jsonify({'error': 'Fehler beim Hinzufügen'}), 500

@app.route('/api/calendar/delete/<int:termin_id>', methods=['DELETE'])
def api_calendar_delete(termin_id):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if termin_loeschen:
        try:
            antwort = termin_loeschen(termin_id)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Calendar Delete Fehler: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Kalender nicht verfügbar'}), 503

@app.route('/api/calendar/erinnerung/add', methods=['POST'])
def api_calendar_erinnerung_add():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    try:
        from plugins.calendar_plugin import erinnerung_hinzufuegen
        data = request.get_json()
        titel = data.get('titel', '')
        datum = data.get('datum', '')
        uhrzeit = data.get('uhrzeit', '08:00')
        antwort = erinnerung_hinzufuegen(titel, datum, uhrzeit)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Erinnerung Add Fehler: {e}")
        return jsonify({'error': str(e)}), 500

# ─── API: EINKAUFSLISTE ───
@app.route('/api/shopping', methods=['GET'])
def api_shopping_list():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if einkaufsliste_anzeigen:
        try:
            result = einkaufsliste_anzeigen()
            return jsonify({'list': result})
        except Exception as e:
            logging.error(f"Shopping GET Fehler: {e}")
    return jsonify({'list': 'Fehler beim Laden'})

@app.route('/api/shopping/add', methods=['POST'])
def api_shopping_add():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if einkaufsliste_hinzufuegen:
        try:
            data = request.get_json()
            item = data.get('item', '').strip()
            if not item:
                return jsonify({'antwort': 'Kein Artikel angegeben.'})
            antwort = einkaufsliste_hinzufuegen(item)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Shopping ADD Fehler: {e}")
    return jsonify({'error': 'Shopping nicht verfügbar'}), 503

@app.route('/api/shopping/remove', methods=['POST'])
def api_shopping_remove():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if einkaufsliste_entfernen:
        try:
            data = request.get_json()
            item = data.get('item', '').strip()
            if not item:
                return jsonify({'antwort': 'Kein Artikel angegeben.'})
            # item kann ID (Zahl) oder Name (String) sein
            antwort = einkaufsliste_entfernen(item)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Shopping REMOVE Fehler: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Shopping nicht verfügbar'}), 503

@app.route('/api/shopping/done', methods=['POST'])
def api_shopping_done():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if einkaufsliste_erledigt:
        try:
            data = request.get_json()
            item = data.get('item', '').strip()
            if not item:
                return jsonify({'antwort': 'Kein Artikel angegeben.'})
            antwort = einkaufsliste_erledigt(item)
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Shopping DONE Fehler: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Shopping nicht verfügbar'}), 503

@app.route('/api/shopping/clear', methods=['POST'])
def api_shopping_clear():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if einkaufsliste_leeren:
        try:
            antwort = einkaufsliste_leeren()
            return jsonify({'antwort': antwort})
        except Exception as e:
            logging.error(f"Shopping CLEAR Fehler: {e}")
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Shopping nicht verfügbar'}), 503

# ─── API: GEDÄCHTNIS ───
@app.route('/api/memory/facts', methods=['GET'])
def api_memory_facts():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if get_facts:
        try:
            facts = get_facts()
            return jsonify({'facts': facts})
        except Exception as e:
            logging.error(f"Memory Fehler: {e}")
    return jsonify({'facts': []})

# ─── API: ROUTINEN ───
@app.route('/api/routines', methods=['GET'])
def api_routines():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    try:
        if routinen_alle is None or _lade_routinen is None:
            return jsonify({'routinen': 'Fehler', 'raw': []})
        result = routinen_alle()
        daten = _lade_routinen()
        raw = daten.get("routinen", [])
        return jsonify({'routinen': result, 'raw': raw})
    except Exception as e:
        logging.error(f"Routines GET Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/run/<int:routine_id>', methods=['POST'])
def api_routines_run(routine_id):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if routine_ausfuehren is None:
        return jsonify({'error': 'Routine-Tool nicht verfügbar'}), 503
    try:
        antwort = routine_ausfuehren(routine_id)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Routine run Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/toggle/<int:routine_id>', methods=['POST'])
def api_routines_toggle(routine_id):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if routine_toggle is None:
        return jsonify({'error': 'Routine-Tool nicht verfügbar'}), 503
    try:
        antwort = routine_toggle(routine_id)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Routine toggle Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/delete/<int:routine_id>', methods=['DELETE'])
def api_routines_delete(routine_id):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if routine_loeschen is None:
        return jsonify({'error': 'Routine-Tool nicht verfügbar'}), 503
    try:
        antwort = routine_loeschen(routine_id)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Routine delete Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/update/<int:routine_id>', methods=['POST'])
def api_routines_update(routine_id):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if routine_aktualisieren is None:
        return jsonify({'error': 'Routine-Tool nicht verfügbar'}), 503
    try:
        data = request.get_json()
        name = data.get('name', '')
        trigger = data.get('trigger', '')
        trigger_wert = data.get('trigger_wert', '')
        aktionen = data.get('aktionen', [])
        wochentage = data.get('wochentage', None)
        if not name or not trigger or not trigger_wert or not aktionen:
            return jsonify({'error': 'Name, Trigger, Wert und Aktionen erforderlich'}), 400
        antwort = routine_aktualisieren(routine_id, name, trigger, trigger_wert, aktionen, wochentage=wochentage)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Routine update Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/add', methods=['POST'])
def api_routines_add():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    try:
        from plugins.routines_plugin import routine_hinzufuegen
        data = request.get_json()
        name = data.get('name', '')
        trigger = data.get('trigger', '')
        trigger_wert = data.get('trigger_wert', '')
        aktionen = data.get('aktionen', [])
        wochentage = data.get('wochentage', None)
        if not name or not trigger or not trigger_wert or not aktionen:
            return jsonify({'error': 'Name, Trigger, Wert und Aktionen erforderlich'}), 400
        antwort = routine_hinzufuegen(name, trigger, trigger_wert, aktionen, wochentage=wochentage)
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Routine add Fehler: {e}")
        return jsonify({'error': str(e)}), 500

# ─── API: SCHEDULER ───
@app.route('/api/routines/scheduler/status', methods=['GET'])
def api_scheduler_status():
    try:
        status_file = Path("scheduler_status.json")
        if status_file.exists():
            with open(status_file, "r") as f:
                data = json.load(f)
                running = data.get("running", False)
                return jsonify({'running': running})
    except Exception as e:
        logging.error(f"Scheduler Status Fehler: {e}")
    return jsonify({'running': False})

@app.route('/api/routines/scheduler/start', methods=['POST'])
def api_scheduler_start():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if starte_scheduler is None:
        return jsonify({'error': 'Scheduler nicht verfügbar'}), 503
    try:
        antwort = starte_scheduler()
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Scheduler Start Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/routines/scheduler/stop', methods=['POST'])
def api_scheduler_stop():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if stoppe_scheduler is None:
        return jsonify({'error': 'Scheduler nicht verfügbar'}), 503
    try:
        antwort = stoppe_scheduler()
        return jsonify({'antwort': antwort})
    except Exception as e:
        logging.error(f"Scheduler Stop Fehler: {e}")
        return jsonify({'error': str(e)}), 500

# ─── API: PROAKTIVE INTELLIGENZ ───
@app.route('/api/proactive/suggestions', methods=['GET'])
def api_proactive_suggestions():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if get_suggestions is None:
        return jsonify({'error': 'Proactive nicht verfügbar'}), 503
    try:
        suggestions = get_suggestions()
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        logging.error(f"Proactive Suggestions Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proactive/accept/<int:index>', methods=['POST'])
def api_proactive_accept(index):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if accept_suggestion is None:
        return jsonify({'error': 'Proactive nicht verfügbar'}), 503
    try:
        result = accept_suggestion(index)
        return jsonify({'result': result})
    except Exception as e:
        logging.error(f"Proactive Accept Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proactive/reject/<int:index>', methods=['POST'])
def api_proactive_reject(index):
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if reject_suggestion is None:
        return jsonify({'error': 'Proactive nicht verfügbar'}), 503
    try:
        result = reject_suggestion(index)
        return jsonify({'result': result})
    except Exception as e:
        logging.error(f"Proactive Reject Fehler: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/proactive/analyze', methods=['POST'])
def api_proactive_analyze():
    if not session.get('authorized', False):
        return jsonify({'error': 'Autorisierung erforderlich'}), 401
    if trigger_analysis is None:
        return jsonify({'error': 'Proactive nicht verfügbar'}), 503
    try:
        result = trigger_analysis()
        return jsonify({'result': result})
    except Exception as e:
        logging.error(f"Proactive Analyze Fehler: {e}")
        return jsonify({'error': str(e)}), 500

# ─── WAKEWORD-API (für optionales Wakeword) ───
_wakeword_triggered = False
_wakeword_lock = threading.Lock()

@app.route('/api/wakeword', methods=['POST'])
def api_wakeword():
    data = request.get_json() or {}
    keyword = data.get('keyword', 'pia')
    with _wakeword_lock:
        global _wakeword_triggered
        _wakeword_triggered = True
    logging.info(f"[Wakeword] '{keyword}' erkannt!")
    return jsonify({"status": "ok", "keyword": keyword})

@app.route('/api/events')
def api_events():
    def generate():
        global _wakeword_triggered
        while True:
            with _wakeword_lock:
                if _wakeword_triggered:
                    _wakeword_triggered = False
                    yield f"data: wakeword\n\n"
                else:
                    yield f": heartbeat\n\n"
            time.sleep(0.5)
    return Response(generate(), mimetype="text/event-stream")

# ─── PUSH-SCHEDULER STARTEN ───
try:
    if start_push_scheduler:
        start_push_scheduler()
        print("[webui] Push-Scheduler gestartet.")
    else:
        print("[webui] Push-Scheduler nicht verfügbar (Plugin fehlt).")
except Exception as e:
    print(f"[webui] Push-Scheduler-Fehler: {e}")

# ─── ROUTINEN-SCHEDULER STARTEN ───
try:
    if starte_scheduler:
        starte_scheduler()
        print("[webui] Routine-Scheduler gestartet.")
except Exception as e:
    print(f"[webui] Routine-Scheduler-Fehler: {e}")

# ─── START ───
if __name__ == '__main__':
    port = 5000
    use_ssl = True

    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        if idx + 1 < len(sys.argv):
            try:
                port = int(sys.argv[idx+1])
            except ValueError:
                pass

    if '--http' in sys.argv or '--no-ssl' in sys.argv:
        use_ssl = False
        print("[webui] HTTP-Modus (kein SSL)")

    ssl_context = None
    if use_ssl:
        try:
            cert_files = [f for f in os.listdir('.') if f.endswith('.pem') and not f.endswith('-key.pem')]
            key_files = [f for f in os.listdir('.') if f.endswith('-key.pem')]
            if cert_files and key_files:
                cert_file = cert_files[0]
                key_file = cert_file.replace('.pem', '-key.pem')
                if key_file in key_files and os.path.exists(cert_file) and os.path.exists(key_file):
                    ssl_context = (cert_file, key_file)
                    print(f"[webui] HTTPS mit {cert_file}")
                else:
                    print("[webui] Zertifikat gefunden, aber dazugehöriger Key fehlt.")
                    use_ssl = False
            else:
                print("[webui] Keine Zertifikate gefunden – starte mit HTTP.")
                use_ssl = False
        except Exception as e:
            print(f"[webui] SSL-Fehler: {e} – starte mit HTTP.")
            use_ssl = False

    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        ssl_context=ssl_context if use_ssl else None
    )