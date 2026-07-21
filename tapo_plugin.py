# plugins/tapo_plugin.py – Tapo Smart Home

import asyncio
import re
import logging
from utils import lade_json

def register(core):
    core.register_command(["licht", "ventilator", "kaffeemaschine", "helligkeit", "farbe", "rgb"], handle_tapo, "Smart Home steuern")

config = lade_json("pia5_konfig.json")
TAPO_EMAIL = config.get("tapo_email", "jwestphal1204@gmail.com")
TAPO_PASSWORD = config.get("tapo_password", "Met@l666")

TAPO_GERAETE = {
    "licht": {"ip": "192.168.178.151", "typ": "lampe"},
    "ventilator": {"ip": "192.168.178.89", "typ": "steckdose"},
    "kaffeemaschine": {"ip": "192.168.178.195", "typ": "steckdose"},
}

FARBEN = {
    "rot": (0, 100), "grün": (120, 100), "blau": (240, 100),
    "gelb": (60, 100), "orange": (30, 100), "lila": (270, 100),
    "weiss": (0, 1), "weiß": (0, 1), "türkis": (180, 100),
    "pink": (330, 100), "gold": (45, 100), "braun": (30, 50),
    "warm": (30, 80), "kalt": (200, 80), "nacht": (30, 20),
}

def rgb_to_hue_sat(r, g, b):
    r, g, b = r/255.0, g/255.0, b/255.0
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    if diff == 0:
        hue = 0
    elif max_val == r:
        hue = 60 * (((g - b) / diff) % 6)
    elif max_val == g:
        hue = 60 * ((b - r) / diff + 2)
    else:
        hue = 60 * ((r - g) / diff + 4)
    saturation = 0 if max_val == 0 else (diff / max_val) * 100
    return int(hue), int(saturation)

async def _steuern(gerät_name, befehl):
    try:
        from tapo import ApiClient
    except ImportError:
        return "Tapo-Bibliothek nicht installiert. Bitte 'pip install tapo' ausführen."
    if gerät_name not in TAPO_GERAETE:
        return f"Gerät '{gerät_name}' nicht gefunden."
    gerät = TAPO_GERAETE[gerät_name]
    ip = gerät["ip"]
    typ = gerät["typ"]
    try:
        client = ApiClient(TAPO_EMAIL, TAPO_PASSWORD)
        if typ == "lampe":
            device = await client.l530(ip)
        elif typ == "steckdose":
            device = await client.p100(ip)
        else:
            return f"Unbekannter Gerätetyp: {typ}"
        befehl = befehl.lower().strip()
        if "rgb" in befehl and typ == "lampe":
            match = re.search(r'rgb\s+(\d+)\s+(\d+)\s+(\d+)', befehl)
            if match:
                r, g, b = map(int, match.groups())
                hue, sat = rgb_to_hue_sat(r, g, b)
                await device.set_hue_saturation(hue, sat)
                return f"RGB ({r},{g},{b}) gesetzt."
        if typ == "lampe":
            for name, (hue, sat) in FARBEN.items():
                if name in befehl:
                    await device.set_hue_saturation(hue, sat)
                    return f"Farbe auf {name} gesetzt."
        if "helligkeit" in befehl and typ == "lampe":
            match = re.search(r'helligkeit\s+(\d+)', befehl)
            if match:
                wert = max(1, min(100, int(match.group(1))))
                await device.set_brightness(wert)
                return f"Helligkeit auf {wert}% gesetzt."
        if "an" in befehl:
            await device.on()
            return f"{gerät_name} eingeschaltet."
        if "aus" in befehl:
            await device.off()
            return f"{gerät_name} ausgeschaltet."
        return "Unbekannter Befehl."
    except Exception as e:
        logging.error(f"Tapo Fehler: {e}")
        return f"Tapo Fehler: {e}"

async def _get_status(gerät_name):
    try:
        from tapo import ApiClient
    except ImportError:
        return None
    if gerät_name not in TAPO_GERAETE:
        return None
    gerät = TAPO_GERAETE[gerät_name]
    ip = gerät["ip"]
    typ = gerät["typ"]
    try:
        client = ApiClient(TAPO_EMAIL, TAPO_PASSWORD)
        if typ == "lampe":
            device = await client.l530(ip)
        elif typ == "steckdose":
            device = await client.p100(ip)
        else:
            return None
        info = await device.get_device_info()
        return info.device_on
    except Exception as e:
        logging.error(f"Status-Fehler {gerät_name}: {e}")
        return None

def tapo_steuern(befehl):
    befehl = befehl.lower().strip()
    gerät_name = None
    for name in TAPO_GERAETE.keys():
        if name in befehl:
            gerät_name = name
            break
    if gerät_name is None:
        if any(kw in befehl for kw in ["helligkeit", "farbe", "rgb"]):
            gerät_name = "licht"
        else:
            gerät_name = "licht"
    try:
        return asyncio.run(_steuern(gerät_name, befehl))
    except Exception as e:
        return f"Fehler: {e}"

def tapo_status(gerät_name=None):
    if gerät_name:
        try:
            status = asyncio.run(_get_status(gerät_name))
            return {gerät_name: status}
        except Exception as e:
            logging.error(f"Status-Fehler {gerät_name}: {e}")
            return {gerät_name: None}
    else:
        status_dict = {}
        for name in TAPO_GERAETE.keys():
            try:
                status_dict[name] = asyncio.run(_get_status(name))
            except Exception as e:
                logging.error(f"Status-Fehler {name}: {e}")
                status_dict[name] = None
        return status_dict

def handle_tapo(befehl):
    """Verarbeitet Tapo-Befehle."""
    return tapo_steuern(befehl)