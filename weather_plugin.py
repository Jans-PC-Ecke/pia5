# plugins/weather_plugin.py – mit Vorhersage (heute/morgen/übermorgen)

import re
import requests
from datetime import datetime, timedelta
from utils import KONFIG, logging

def register(core):
    core.register_command(["wetter"], handle_weather, "Wetter abfragen (heute/morgen/übermorgen)")

def wetter_holen(stadt="Eschwege", tage=0):
    """
    Holt das Wetter für heute (tage=0), morgen (tage=1) oder übermorgen (tage=2).
    """
    api_key = KONFIG.get("openweather_api_key")
    if not api_key:
        return "Kein OpenWeather API-Key eingetragen."
    
    stadt = stadt.strip()
    if not stadt or stadt in ["#", ""]:
        stadt = "Eschwege"
    
    # Hole 5-Tage-Vorhersage (alle 3 Stunden)
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={stadt}&appid={api_key}&units=metric&lang=de"
    
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        if data.get("cod") != "200":
            return f"Stadt '{stadt}' nicht gefunden."
        
        ziel_datum = datetime.now().date() + timedelta(days=tage)
        stadt_name = data["city"]["name"]
        
        beste_treffer = []
        for entry in data["list"]:
            dt = datetime.fromtimestamp(entry["dt"])
            if dt.date() == ziel_datum:
                if 12 <= dt.hour <= 15:
                    beste_treffer.append((dt, entry))
                else:
                    beste_treffer.append((dt, entry))
        
        if not beste_treffer:
            tage_text = ["heute", "morgen", "übermorgen"][tage]
            return f"Keine Wetterdaten für {tage_text} in {stadt_name}."
        
        beste_treffer.sort(key=lambda x: (abs(x[0].hour - 12), x[0]))
        dt, wetter = beste_treffer[0]
        
        beschreibung = wetter["weather"][0]["description"]
        temp = wetter["main"]["temp"]
        gefuehlt = wetter["main"]["feels_like"]
        
        tage_text = ["heute", "morgen", "übermorgen"][tage]
        tageszeit = "Nacht" if dt.hour < 6 or dt.hour >= 21 else "Tag"
        
        antwort = f"In {stadt_name} ({tage_text}): {beschreibung.capitalize()}, {temp:.1f} °C (gefühlt {gefuehlt:.1f} °C)."
        return antwort
        
    except requests.HTTPError as e:
        if e.response.status_code == 401:
            return "Wetter-API-Key ungültig oder abgelaufen."
        logging.error(f"Wetter-Abfrage fehlgeschlagen: {e}")
        return "Wetterdienst gerade nicht erreichbar."
    except requests.RequestException as e:
        logging.error(f"Wetter-Abfrage fehlgeschlagen: {e}")
        return "Wetterdienst gerade nicht erreichbar."

def handle_weather(befehl):
    clean = befehl.lower().strip()
    
    stadt = "Eschwege"
    if "in " in clean:
        stadt = clean.split("in ", 1)[-1].strip()
        stadt = re.sub(r'\b(heute|morgen|übermorgen)\b', '', stadt).strip()
        clean = clean.replace(f" in {stadt}", "").strip()
    
    tage = 0
    if "übermorgen" in clean:
        tage = 2
        clean = clean.replace("übermorgen", "").strip()
    elif "morgen" in clean:
        tage = 1
        clean = clean.replace("morgen", "").strip()
    elif "heute" in clean:
        tage = 0
        clean = clean.replace("heute", "").strip()
    
    if not stadt or stadt == "Eschwege":
        rest = clean.replace("wetter", "").strip()
        if rest:
            stadt = rest
    
    return wetter_holen(stadt, tage)

def tools_holen():
    return [
        ("wetter_holen", wetter_holen, "Wetter"),
        ("handle_weather", handle_weather, "Wetter"),
    ]