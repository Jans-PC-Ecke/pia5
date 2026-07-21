# intent_plugin.py – Absichtserkennung (Keyword + semantisch) – FINAL

import re
from utils import lade_json, speichere_json, logging

def register(core):
    core.register_command(
        ["intent", "intents", "trainiere", "lern", "vergiss"],
        handle_intent,
        "Absichtserkennung (Keyword + semantisch)"
    )

INTENT_FILE = "intents.json"

# ─── CHROMA FÜR INTENTS (Lazy Loading) ───
_chroma_intent_client = None
_intent_model = None
_INTENT_CHROMA_AVAILABLE = False

def _init_intent_chroma():
    global _chroma_intent_client, _intent_model, _INTENT_CHROMA_AVAILABLE
    if _chroma_intent_client is not None:
        return True
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        _chroma_intent_client = chromadb.PersistentClient(path="./chroma_intent_data")
        _intent_model = SentenceTransformer("all-MiniLM-L6-v2")
        _INTENT_CHROMA_AVAILABLE = True
        logging.info("[Intent] ChromaDB für semantische Erkennung geladen")
        return True
    except ImportError:
        logging.warning("[Intent] ChromaDB nicht installiert – nur Keyword-Matching")
        return False
    except Exception as e:
        logging.warning(f"[Intent] Semantische Erkennung nicht verfügbar: {e}")
        return False

def _get_intent_collection():
    if not _init_intent_chroma():
        return None
    try:
        return _chroma_intent_client.get_collection("intents")
    except:
        return _chroma_intent_client.create_collection("intents")

def _index_intents():
    collection = _get_intent_collection()
    if collection is None:
        return
    intents = _get_intents()
    try:
        if collection.count() > 0:
            return
    except:
        pass
    
    for name, data in intents.items():
        for keyword in data.get("keywords", []):
            try:
                embedding = _intent_model.encode(keyword).tolist()
                collection.add(
                    embeddings=[embedding],
                    metadatas=[{"intent": name, "keyword": keyword, "action": data.get("action", "")}],
                    ids=[f"{name}_{keyword.replace(' ', '_')}"]
                )
            except:
                pass
    logging.info(f"[Intent] {len(intents)} Intents indiziert")

def _get_intents():
    default = {
        "intents": {
            "einkaufsliste": {
                "keywords": ["einkaufsliste", "einkauf", "liste", "shopping"],
                "action": "einkaufsliste"
            },
            "wetter": {
                "keywords": ["wetter", "temperatur", "regnet", "sonne", "wetterbericht", "wie wird das wetter"],
                "action": "wetter"
            },
            "uhrzeit": {
                "keywords": ["uhrzeit", "wie spät", "datum", "wochentag", "zeit"],
                "action": "uhrzeit"
            },
            "termin": {
                "keywords": ["termin", "erinnerung", "meeting", "kalender"],
                "action": "termin heute"
            },
            "daily": {
                "keywords": ["daily", "heute", "übersicht", "was muss ich", "tägliche übersicht"],
                "action": "daily"
            },
            "licht_an": {
                "keywords": ["licht an", "beleuchtung an", "lampe an", "mach hell"],
                "action": "licht an"
            },
            "licht_aus": {
                "keywords": ["licht aus", "beleuchtung aus", "lampe aus", "mach dunkel"],
                "action": "licht aus"
            },
            "ventilator_an": {
                "keywords": ["ventilator an", "venti an"],
                "action": "ventilator an"
            },
            "ventilator_aus": {
                "keywords": ["ventilator aus", "venti aus"],
                "action": "ventilator aus"
            },
            "kaffeemaschine_an": {
                "keywords": ["kaffeemaschine an", "kaffee an"],
                "action": "kaffeemaschine an"
            },
            "kaffeemaschine_aus": {
                "keywords": ["kaffeemaschine aus", "kaffee aus"],
                "action": "kaffeemaschine aus"
            },
            "alarm": {
                "keywords": ["alarm", "wecker", "timer", "erinnere mich"],
                "action": None  # Wird separat behandelt
            },
            "denken": {
                "keywords": ["was denkst du", "denkst du", "meinst du", "was weißt du über"],
                "action": None  # Wird separat behandelt
            }
        }
    }
    data = lade_json(INTENT_FILE, default)
    if "intents" not in data:
        data["intents"] = default["intents"]
        speichere_json(INTENT_FILE, data)
    return data["intents"]

def _save_intents(intents):
    speichere_json(INTENT_FILE, {"intents": intents})

def _normalize(text):
    return re.sub(r'[^\w\s]', '', text.lower())

def _is_shopping_item(text):
    shopping_keywords = [
        "milch", "eier", "brot", "käse", "käser", "butter", "joghurt", "quark",
        "sahne", "eis", "kuchen", "schokolade", "wurst", "schinken", "salami",
        "hähnchen", "fisch", "lachs", "apfel", "banane", "orange", "zitrone",
        "traube", "erdbeere", "himbeere", "pfirsich", "kirsche", "birne",
        "kartoffel", "reis", "nudel", "mehl", "zucker", "salz", "pfeffer",
        "öl", "essig", "tomate", "gurke", "salat", "möhre", "karotte",
        "zwiebel", "knoblauch", "pilz", "paprika", "brokkoli", "blumenkohl",
        "saft", "wasser", "bier", "wein", "cola", "limonade", "kaffee",
        "tee", "kakao", "pizza", "pommes", "chips", "nüsse", "mandeln",
        "honig", "marmelade", "nutella", "pesto", "butter", "margarine"
    ]
    text_lower = text.lower()
    for kw in shopping_keywords:
        if kw in text_lower or text_lower in kw:
            return True
    return False

def recognize_intent_semantic(text):
    if not _INTENT_CHROMA_AVAILABLE:
        return None, None
    
    collection = _get_intent_collection()
    if collection is None:
        return None, None
    
    _index_intents()
    
    try:
        query_embedding = _intent_model.encode(text).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
            include=["metadatas", "distances"]
        )
        
        if results and results["metadatas"]:
            best = results["metadatas"][0][0]
            distance = results["distances"][0][0] if results.get("distances") else 1.0
            relevanz = 1 - distance
            
            if relevanz > 0.7:
                intent = best.get("intent")
                action = best.get("action")
                logging.info(f"[Intent] Semantisch: {intent} → {action} (Relevanz: {relevanz:.2f})")
                return intent, action
    except Exception as e:
        logging.debug(f"Semantische Suche Fehler: {e}")
    
    return None, None

def recognize_intent(text):
    """
    Kombinierte Intent-Erkennung in dieser Reihenfolge:
    1. Keyword-Matching (schnell, exakt)
    2. Teilwort-Matching (z.B. "wetterbericht" → "wetter")
    3. Semantische Suche (ChromaDB)
    4. Shopping-Fallback
    """
    intents = _get_intents()
    text_norm = _normalize(text)
    
    # ─── 1. Exaktes Keyword-Matching ───
    for name, data in intents.items():
        for keyword in data.get("keywords", []):
            keyword_norm = _normalize(keyword)
            if keyword_norm in text_norm:
                logging.info(f"[Intent] Keyword-Match: {name} → {data.get('action')}")
                return name, data.get("action")
    
    # ─── 2. Teilwort-Matching ───
    for name, data in intents.items():
        for keyword in data.get("keywords", []):
            keyword_norm = _normalize(keyword)
            # Prüfe, ob Keyword im Text ODER Text im Keyword
            if keyword_norm in text_norm or text_norm in keyword_norm:
                logging.info(f"[Intent] Teilwort-Match: {name} → {data.get('action')}")
                return name, data.get("action")
    
    # ─── 3. Semantische Suche ───
    intent, action = recognize_intent_semantic(text)
    if intent and action:
        return intent, action
    
    # ─── 4. Shopping-Fallback ───
    if _is_shopping_item(text):
        try:
            from plugins.shopping_plugin import einkaufsliste_hinzufuegen
            result = einkaufsliste_hinzufuegen(text, "1", "")
            return "einkaufsliste_direkt", result
        except:
            pass
    
    # ─── 5. Einzelnes Wort als Shopping ───
    if len(text.split()) == 1 and len(text) > 2:
        try:
            from plugins.shopping_plugin import einkaufsliste_hinzufuegen
            result = einkaufsliste_hinzufuegen(text, "1", "")
            return "einkaufsliste_direkt", result
        except:
            pass
    
    return None, None

def train_intent(intent_name, keywords, action=None):
    intents = _get_intents()
    if intent_name in intents:
        existing = intents[intent_name].get("keywords", [])
        for kw in keywords:
            if kw not in existing:
                existing.append(kw)
        if action:
            intents[intent_name]["action"] = action
    else:
        intents[intent_name] = {"keywords": keywords, "action": action or intent_name}
    _save_intents(intents)
    
    if _INTENT_CHROMA_AVAILABLE:
        try:
            collection = _get_intent_collection()
            if collection is not None and _intent_model is not None:
                for kw in keywords:
                    embedding = _intent_model.encode(kw).tolist()
                    collection.add(
                        embeddings=[embedding],
                        metadatas=[{"intent": intent_name, "keyword": kw, "action": action or intent_name}],
                        ids=[f"{intent_name}_{kw.replace(' ', '_')}"]
                    )
        except:
            pass
    
    return f"✅ Intent '{intent_name}' trainiert ({len(keywords)} Keywords)"

def delete_intent(intent_name):
    intents = _get_intents()
    if intent_name in intents:
        del intents[intent_name]
        _save_intents(intents)
        if _INTENT_CHROMA_AVAILABLE:
            try:
                collection = _get_intent_collection()
                if collection is not None:
                    results = collection.get(where={"intent": intent_name})
                    if results and results["ids"]:
                        collection.delete(ids=results["ids"])
            except:
                pass
        return f"🗑️ Intent '{intent_name}' gelöscht."
    return f"Intent '{intent_name}' nicht gefunden."

def list_intents():
    intents = _get_intents()
    if not intents:
        return "Keine Intents vorhanden."
    ausgabe = "📋 Bekannte Intents:\n"
    for name, data in intents.items():
        keywords = data.get("keywords", [])
        ausgabe += f"  • {name}: {', '.join(keywords[:3])}"
        if len(keywords) > 3:
            ausgabe += f" (+{len(keywords)-3} weitere)"
        ausgabe += "\n"
    return ausgabe.strip()

def handle_intent(befehl):
    clean = befehl.lower().strip()
    parts = clean.split(maxsplit=1)
    cmd = parts[0] if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if cmd in ["intent", "intents"] and not args:
        return list_intents()

    if cmd in ["trainiere", "lern", "train", "teach"]:
        if not args or ":" not in args:
            return "Format: 'trainiere <intent>: <keyword1>, <keyword2>'"
        name, rest = args.split(":", 1)
        name = name.strip()
        keywords = [k.strip() for k in rest.split(",") if k.strip()]
        return train_intent(name, keywords)

    if cmd in ["vergiss", "delete", "remove"] and args:
        return delete_intent(args.strip())

    return None

def tools_holen():
    return [
        ("recognize_intent", recognize_intent, "Absichtserkennung"),
        ("train_intent", train_intent, "Intent trainieren"),
        ("delete_intent", delete_intent, "Intent löschen"),
        ("list_intents", list_intents, "Intents anzeigen"),
    ]