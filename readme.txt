
---

### 📁 `templates/README.md`

```markdown
# PIA 5 – Templates (WebUI)

Dieser Ordner enthält die HTML-Templates für die Web-Oberfläche.

| Datei | Beschreibung |
|-------|--------------|
| `login.html` | Login-Seite mit PIN-Eingabe |
| `index_simple.html` | Hauptoberfläche (Dashboard mit allen Funktionen) |

## Anpassungen

- **Styling:** CSS ist direkt in den HTML-Dateien eingebettet.
- **Dark/Light-Mode:** Wird im Browser gespeichert (`localStorage`).
- **JavaScript:** Alle Funktionen sind in den HTML-Dateien enthalten.

## API-Endpunkte

Die WebUI kommuniziert mit den folgenden API-Endpunkten:

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/command` | POST | Befehl ausführen |
| `/api/speech` | POST | Spracheingabe verarbeiten |
| `/api/routines` | GET | Routinen laden |
| `/api/routines/update/<id>` | POST | Routine aktualisieren |
| `/api/shopping` | GET | Einkaufsliste laden |
| `/api/shopping/add` | POST | Artikel hinzufügen |
| `/api/shopping/remove` | POST | Artikel entfernen |
| `/api/shopping/done` | POST | Artikel als erledigt markieren |
| `/api/calendar/today` | GET | Heutige Termine |
| `/api/calendar/month/<year>/<month>` | GET | Monatsübersicht |
| `/api/tapo/status` | GET | Smart-Home-Status |
| `/api/tapo/<device>/<action>` | POST | Gerät steuern |
| `/api/proactive/suggestions` | GET | Proaktive Vorschläge |
| `/api/proactive/analyze` | POST | Analyse starten |
| `/api/user/current` | GET | Aktuellen User abfragen |

## Hinweise

- Die WebUI ist **nicht** für mobile Geräte optimiert (aber responsive).
- Für eine Produktiv-Umgebung sollte ein **WSGI-Server** (z.B. Gunicorn) verwendet werden.