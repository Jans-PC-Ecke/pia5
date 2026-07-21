#!/usr/bin/env python3
# ki/list_facts.py – Zeigt alle Fakten aus der JSON-Datei

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
USERNAME = "jan"
MEMORY_FILE = BASE_DIR / f"memory_{USERNAME}.json"

with open(MEMORY_FILE, "r") as f:
    data = json.load(f)

facts = data.get("facts", [])
if not facts:
    print("📭 Keine Fakten gespeichert.")
else:
    print(f"📋 {len(facts)} Fakten:\n")
    for i, f in enumerate(facts):
        print(f"{i+1:3d}. {f['fact']} (Quelle: {f.get('source', 'user')})")