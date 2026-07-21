# plugin_loader.py – Lädt alle Plugins aus dem plugins/-Ordner

import importlib.util
import logging
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent / "plugins"

def load_plugins(core):
    """Durchsucht den plugins/-Ordner, importiert jedes Modul und ruft register(core) auf."""
    if not PLUGIN_DIR.exists():
        PLUGIN_DIR.mkdir()
        logging.info(f"[Plugins] Ordner {PLUGIN_DIR} erstellt.")
        return

    for file in PLUGIN_DIR.glob("*.py"):
        if file.name.startswith("_"):
            continue
        module_name = file.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                module.register(core)
                logging.info(f"[Plugins] Plugin '{module_name}' geladen.")
            else:
                logging.warning(f"[Plugins] Plugin '{module_name}' hat keine register()-Funktion.")
        except Exception as e:
            logging.error(f"[Plugins] Fehler beim Laden von '{module_name}': {e}")