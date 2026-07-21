# PIA 5 – KI-Skripte (Eigene Tools)

Dieser Ordner enthält meine persönlichen Skripte für die Kommandozeile – **kein LLM**, sondern nützliche Helfer für PIA.

## Skripte

| Datei | Beschreibung |
|-------|--------------|
| `export_memory.sh` | Backup der `memory_jan.json` in `backups/` |
| `list_facts.py` | Alle Fakten aus der JSON-Datei anzeigen |
| `search_memory.py` | Semantische Suche in ChromaDB (Terminal) |
| `batch_import.py` | Massen-Import von Fakten aus einer TXT-Datei |
| `import_memory_to_chroma.py` | (Optional) JSON → ChromaDB importieren |

## Nutzung

```bash
# Backup erstellen
./export_memory.sh

# Alle Fakten anzeigen
python3 list_facts.py

# Semantische Suche
python3 search_memory.py "Pizza"

# Fakten aus TXT importieren
python3 batch_import.py fakten.txt