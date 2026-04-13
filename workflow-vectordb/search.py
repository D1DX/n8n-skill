"""Compact workflow search -- designed for inline use by AI coding assistants.

Output is minimal: name, score, path. One line per result.

Usage:
  python search.py "webhook receives data and writes to postgres"
  python search.py "slack AI chatbot with RAG" -n 5
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb
import voyageai
from dotenv import load_dotenv

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "n8n_workflows"


def search(query: str, n: int = 3) -> list[dict]:
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    embedding = vo.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    results = collection.query(
        query_embeddings=[embedding], n_results=n * 4,
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    try:
        rr = vo.rerank(query=query, documents=docs, model="rerank-2.5-lite", top_k=n, truncation=True)
        return [{"score": round(r.relevance_score, 3), "name": metas[r.index]["name"],
                 "nodes": metas[r.index]["node_count"], "source": metas[r.index]["source"],
                 "path": metas[r.index]["json_path"]} for r in rr.results]
    except Exception:
        return [{"score": round(max(0, 1 - results["distances"][0][i]), 3), "name": metas[i]["name"],
                 "nodes": metas[i]["node_count"], "source": metas[i]["source"],
                 "path": metas[i]["json_path"]} for i in range(min(n, len(metas)))]


if __name__ == "__main__":
    args = sys.argv[1:]
    n = 3
    for i, a in enumerate(args):
        if a == "-n" and i + 1 < len(args):
            n = int(args[i + 1])
            args = args[:i] + args[i + 2:]
            break
    q = " ".join(args) if args else input("Query: ")
    hits = search(q, n)
    for i, h in enumerate(hits):
        print(f"{i+1}. [{h['score']:.3f}] {h['name']} ({h['nodes']} nodes, {h['source']})")
        if h["path"]:
            print(f"   {h['path']}")
