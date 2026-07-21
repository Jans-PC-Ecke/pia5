#!/usr/bin/env python3
# ki/import_memory_to_chroma.py – Importiert Fakten aus JSON in ChromaDB

import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb

# Pfade: Skript liegt in pia5/ki/, die JSON liegt in pia5/
BASE_DIR = Path(__file__).parent.parent
USERNAME = "jan"
MEMORY_FILE = BASE_DIR / f"memory_{USERNAME}.json"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

def import_facts():
    if not MEMORY_FILE.exists():
        print(f"❌ {MEMORY_FILE} nicht gefunden.")
        return

    with open(MEMORY_FILE, "r") as f:
        data = json.load(f)

    facts = data.get("facts", [])
    if not facts:
        print("📭 Keine Fakten zum Importieren.")
        return

    print(f"📥 Lade {len(facts)} Fakten in ChromaDB...")

    client = chromadb.Client()
    collection_name = USERNAME
    try:
        collection = client.get_collection(collection_name)
        print(f"ℹ️ Collection '{collection_name}' existiert bereits – lösche sie.")
        client.delete_collection(collection_name)
    except:
        pass

    collection = client.create_collection(collection_name)
    print(f"✅ Collection '{collection_name}' erstellt.")

    model = SentenceTransformer(EMBEDDING_MODEL)

    for idx, fact in enumerate(facts):
        text = fact["fact"]
        embedding = model.encode(text).tolist()
        collection.add(
            embeddings=[embedding],
            metadatas=[{"fact": text, "source": fact.get("source", "user"), "timestamp": fact.get("timestamp", "")}],
            ids=[str(idx)]
        )
        print(f"  {idx+1}/{len(facts)}: {text[:50]}...")

    print(f"✅ Alle {len(facts)} Fakten importiert.")

if __name__ == "__main__":
    import_facts()