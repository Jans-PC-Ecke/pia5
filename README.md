# PIA 5 – Dein persönlicher KI-Assistent (ohne LLM)

## Was ist PIA 5?

PIA 5 ist ein **offline-fähiger, proaktiver Sprachassistent** – kein Cloud-LLM, sondern ein intelligentes System aus:
- **RAG-Gedächtnis** (ChromaDB) – semantische Suche in deinen Fakten
- **Mustererkennung** – lernt deine Gewohnheiten aus Zeit, Sequenzen & Kontext
- **Proaktive Vorschläge** – analysiert Fakten, Kalender & Einkaufsliste
- **Intent-Erkennung** – versteht deine Befehle (Keyword + semantisch)
- **Kontextbehaftete Unterhaltung** – behält den Gesprächsverlauf im Blick

## Systemanforderungen

- **RAM:** 80–150 MB beim Start, 300–500 MB im Betrieb
- **CPU:** i5-2450M (2 Kerne, 2,5 GHz) – völlig ausreichend
- **Speicher:** ~500 MB für Python + ChromaDB
- **OS:** Linux (Ubuntu/Mint empfohlen)

## Installation

```bash
# 1. Repository klonen
git clone <repo-url>
cd pia5

# 2. Virtuelle Umgebung (optional)
python3 -m venv venv
source venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Konfiguration anpassen
cp pia5_konfig.json.example pia5_konfig.json
# → API-Keys für OpenWeather & Telegram eintragen

# 5. Starten
python3 webui.py --port 5000