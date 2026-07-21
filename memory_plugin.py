# plugins/memory_plugin.py – Persönliches Gedächtnis (RAG) – FINAL

import json
import re
from datetime import datetime
from pathlib import Path
from utils import lade_json, speichere_json, logging

# ─── CHROMADB (Lazy Loading) ───
CHROMA_AVAILABLE = False
_chroma_client = None
_embedding_model = None
_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def _init_chroma():
    global CHROMA_AVAILABLE, _chroma_client, _embedding_model
    if _chroma_client is not None:
        return True
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        _chroma_client = chromadb.PersistentClient(path="./chroma_data")
        _embedding_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
        CHROMA_AVAILABLE = True
        logging.info("[Memory] ChromaDB geladen")
        return True
    except ImportError:
        logging.warning("[Memory] ChromaDB nicht installiert – nur exakte Suche")
        CHROMA_AVAILABLE = False
        return False
    except Exception as e:
        logging.error(f"[Memory] ChromaDB Fehler: {e}")
        CHROMA_AVAILABLE = False
        return False

def register(core):
    core.register_command(
        ["merke", "erinnere dich", "was weißt du", "erinnerst du dich", "vergiss", "suche", "liste"],
        handle_memory,
        "Persönliches Gedächtnis"
    )
    core.register_command(
        ["was denkst du", "denkst du", "meinst du"],
        handle_think,
        "Fakten kombinieren"
    )

def _get_current_user():
    try:
        active_file = Path("active_user.json")
        if active_file.exists():
            with open(active_file, "r") as f:
                data = json.load(f)
            return data.get("username", "jan")
    except:
        pass
    return "jan"

def _get_memory_file(username=None):
    if username is None:
        username = _get_current_user()
    return f"memory_{username}.json"

def _get_memory(username=None):
    file = _get_memory_file(username)
    return lade_json(file, {
        "facts": [],
        "conversations": [],
        "preferences": {},
        "last_updated": None
    })

def _save_memory(data, username=None):
    file = _get_memory_file(username)
    data["last_updated"] = datetime.now().isoformat()
    speichere_json(file, data)

def _get_collection(username):
    if not _init_chroma():
        return None
    try:
        return _chroma_client.get_collection(username)
    except:
        return _chroma_client.create_collection(username)

# ─── KERNLOGIK ───
def add_fact(fact, source="user", username=None):
    if username is None:
        username = _get_current_user()
    memory = _get_memory(username)
    for existing in memory["facts"]:
        if existing["fact"].lower() == fact.lower():
            return f"ℹ️ Fakt existiert bereits: {fact}"
    new_fact = {
        "fact": fact,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }
    memory["facts"].append(new_fact)
    if len(memory["facts"]) > 200:
        memory["facts"] = memory["facts"][-200:]
    _save_memory(memory, username)

    if _init_chroma():
        try:
            collection = _get_collection(username)
            if collection is not None and _embedding_model is not None:
                embedding = _embedding_model.encode(fact).tolist()
                doc_id = str(len(memory["facts"]) - 1)
                collection.add(
                    embeddings=[embedding],
                    metadatas=[{"fact": fact, "source": source, "timestamp": new_fact["timestamp"]}],
                    ids=[doc_id]
                )
        except Exception as e:
            logging.error(f"ChromaDB Fehler: {e}")
    return f"✅ Merke mir: {fact}"

def get_facts(query=None, username=None, limit=10):
    if username is None:
        username = _get_current_user()
    if query and _init_chroma():
        try:
            collection = _get_collection(username)
            if collection is not None and _embedding_model is not None:
                query_embedding = _embedding_model.encode(query).tolist()
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    include=["metadatas", "distances"]
                )
                if results and results["metadatas"]:
                    facts = []
                    for i, meta in enumerate(results["metadatas"][0]):
                        facts.append({
                            "fact": meta.get("fact", ""),
                            "source": meta.get("source", "user"),
                            "timestamp": meta.get("timestamp", ""),
                            "relevanz": round(1 - results["distances"][0][i], 3) if results.get("distances") else None
                        })
                    return facts
        except Exception as e:
            logging.error(f"ChromaDB Query Fehler: {e}")
    memory = _get_memory(username)
    facts = memory["facts"]
    if query:
        query_lower = query.lower()
        return [f for f in facts if query_lower in f["fact"].lower()][:limit]
    return facts[:limit]

def delete_fact(fact_id, username=None):
    if username is None:
        username = _get_current_user()
    memory = _get_memory(username)
    if 0 <= fact_id < len(memory["facts"]):
        deleted = memory["facts"].pop(fact_id)
        _save_memory(memory, username)
        if _init_chroma():
            try:
                collection = _get_collection(username)
                if collection is not None:
                    collection.delete(ids=[str(fact_id)])
            except:
                pass
        return f"🗑️ Fakt gelöscht: {deleted['fact']}"
    return f"❌ Fakt mit ID {fact_id} nicht gefunden."

def list_facts(username=None):
    if username is None:
        username = _get_current_user()
    facts = get_facts(query=None, username=username, limit=50)
    if not facts:
        return "📭 Keine Fakten gespeichert."
    ausgabe = "📋 Deine gespeicherten Fakten:\n"
    for i, f in enumerate(facts):
        ausgabe += f"  {i+1}. {f['fact']}\n"
    return ausgabe.strip()

def search_facts(query, username=None):
    if username is None:
        username = _get_current_user()
    facts = get_facts(query, username=username, limit=5)
    if not facts:
        return f"🔍 Keine relevanten Fakten zu '{query}' gefunden."
    ausgabe = f"🔍 Gefundene Fakten zu '{query}':\n"
    for f in facts:
        ausgabe += f"  • {f['fact']}"
        if f.get('relevanz'):
            ausgabe += f" (Relevanz: {f['relevanz']:.2f})"
        ausgabe += "\n"
    return ausgabe.strip()

# ─── CHAT-KONTEXT ───
def add_to_conversation(role, content, username=None):
    if username is None:
        username = _get_current_user()
    if not content or len(content) > 500:
        return
    memory = _get_memory(username)
    if "conversations" not in memory:
        memory["conversations"] = []
    memory["conversations"].append({
        "role": role,
        "content": content[:500],
        "timestamp": datetime.now().isoformat()
    })
    if len(memory["conversations"]) > 20:
        memory["conversations"] = memory["conversations"][-20:]
    _save_memory(memory, username)

def get_conversation_context(username=None, limit=5):
    if username is None:
        username = _get_current_user()
    memory = _get_memory(username)
    conv = memory.get("conversations", [])
    return conv[-limit:] if conv else []

def get_conversation_as_text(username=None, limit=5):
    conv = get_conversation_context(username, limit)
    if not conv:
        return ""
    text = "📝 Vorherige Unterhaltung:\n"
    for entry in conv:
        role = "User" if entry["role"] == "user" else "Pia"
        text += f"{role}: {entry['content']}\n"
    return text

# ─── "WAS DENKST DU?" ───
def handle_think(befehl):
    clean = befehl.lower().strip()
    thema = re.sub(r'(?:was denkst du|denkst du|meinst du|was weißt du)\s+(?:über|von|zu)?\s*', '', befehl).strip()
    if not thema:
        return "Was soll ich durchdenken?"
    
    username = _get_current_user()
    
    # Entferne Satzzeichen für bessere Suche
    thema_clean = re.sub(r'[^\w\s]', '', thema)
    facts = get_facts(query=thema_clean, username=username, limit=10)
    
    if not facts:
        return f"Ich habe noch nichts über '{thema}' gespeichert. Sag 'merke: ...' und ich lerne dazu!"
    
    antwort = f"🧠 *Was ich über '{thema}' denke:*\n\n"
    antwort += "📖 *Dazu habe ich diese Fakten:*\n"
    for i, f in enumerate(facts[:5], 1):
        antwort += f"  {i}. {f['fact']}\n"
    
    antwort += "\n💡 *Meine Gedanken:*\n"
    combined = " ".join([f["fact"].lower() for f in facts])
    if "mag" in combined or "liebe" in combined:
        antwort += f"• Du magst offenbar Dinge, die mit '{thema}' zu tun haben.\n"
    if len(facts) >= 3:
        antwort += f"• Du hast {len(facts)} Fakten dazu – das ist dir wichtig!\n"
    
    kontext = get_conversation_as_text(username, limit=3)
    if kontext:
        antwort += f"\n{kontext}"
    
    antwort += "\n🤔 Was meinst du? Sag 'merke: ...' für neue Fakten!"
    return antwort

# ─── HAUPTBEFEHLE ───
def handle_memory(befehl):
    clean = befehl.lower().strip()
    username = _get_current_user()

    if "merke" in clean or "erinnere dich" in clean:
        text = re.sub(r'(?:merke|erinnere dich)\s+', '', befehl).strip()
        if text:
            return add_fact(text, username=username)
        return "Was soll ich mir merken?"

    if "was weißt du" in clean and "über mich" in clean:
        facts = get_facts(query=None, username=username, limit=20)
        if not facts:
            return "Ich habe noch nichts über dich gespeichert. Sag mir etwas!"
        ausgabe = "📖 Das weiß ich über dich:\n"
        for f in facts[:10]:
            ausgabe += f"  • {f['fact']}\n"
        if len(facts) > 10:
            ausgabe += f"  ... und {len(facts)-10} weitere."
        return ausgabe.strip()

    if "erinnerst du dich" in clean:
        query = re.sub(r'erinnerst du dich an\s+', '', befehl).strip()
        if query:
            return search_facts(query, username)
        return "Woran soll ich mich erinnern?"

    if "suche" in clean:
        query = re.sub(r'suche\s+', '', befehl).strip()
        if query:
            return search_facts(query, username)
        return "Was soll ich suchen?"

    if "vergiss" in clean and "fakt" in clean:
        match = re.search(r'vergiss\s+fakt\s+(\d+)', clean)
        if match:
            fakt_id = int(match.group(1)) - 1
            return delete_fact(fakt_id, username)
        return "Bitte gib eine Fakt-ID an: 'vergiss Fakt 3'"

    if "liste" in clean or "alle fakten" in clean:
        return list_facts(username)

    return "Gedächtnis-Befehl nicht erkannt. Nutze: 'merke', 'was weißt du', 'suche', 'liste', 'vergiss Fakt X'."

def tools_holen():
    return [
        ("add_fact", add_fact, "Gedächtnis"),
        ("get_facts", get_facts, "Gedächtnis"),
        ("delete_fact", delete_fact, "Gedächtnis"),
        ("list_facts", list_facts, "Gedächtnis"),
        ("search_facts", search_facts, "Gedächtnis"),
        ("handle_think", handle_think, "Fakten kombinieren"),
        ("add_to_conversation", add_to_conversation, "Chat-Kontext"),
        ("get_conversation_context", get_conversation_context, "Chat-Kontext"),
    ]