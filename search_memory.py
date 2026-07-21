#!/usr/bin/env python3
# ki/search_memory.py – Semantische Suche im persönlichen Gedächtnis

import sys
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
USERNAME = "jan"
MODEL = "all-MiniLM-L6-v2"

def search(query, n=5):
    client = chromadb.Client()
    try:
        collection = client.get_collection(USERNAME)
    except:
        print("❌ ChromaDB-Collection nicht gefunden. Führe zuerst 'import_memory_to_chroma.py' aus.")
        return

    model = SentenceTransformer(MODEL)
    q_embedding = model.encode(query).tolist()
    results = collection.query(query_embeddings=[q_embedding], n_results=n)

    if not results or not results["metadatas"]:
        print("❌ Keine Ergebnisse.")
        return

    print(f"\n🔍 Suche nach: '{query}'\n")
    for i, meta in enumerate(results["metadatas"][0]):
        distance = results["distances"][0][i]
        relevanz = 1 - distance
        print(f"{i+1}. {meta['fact']} (Relevanz: {relevanz:.3f})")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Nutzung: python3 search_memory.py <Suchbegriff>")
        sys.exit(1)
    search(" ".join(sys.argv[1:]))