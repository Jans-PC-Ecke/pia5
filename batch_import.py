#!/usr/bin/env python3
# ki/batch_import.py – Importiert Fakten aus einer Textdatei (eine Zeile = ein Fakt)

import sys
from pathlib import Path
import requests

BASE_DIR = Path(__file__).parent.parent

def import_facts_from_file(filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"❌ Datei {filepath} nicht gefunden.")
        return

    with open(filepath, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        print("📭 Keine Fakten in der Datei.")
        return

    print(f"📥 Importiere {len(lines)} Fakten...")

    for i, line in enumerate(lines):
        response = requests.post(
            "http://localhost:5000/api/command",
            json={"befehl": f"merke: {line}"}
        )
        if response.status_code == 200:
            print(f"  {i+1}/{len(lines)}: ✅ {line}")
        else:
            print(f"  {i+1}/{len(lines)}: ❌ Fehler bei '{line}'")

    print("✅ Fertig.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Nutzung: python3 batch_import.py <datei.txt>")
        sys.exit(1)
    import_facts_from_file(sys.argv[1])