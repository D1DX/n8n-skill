"""Full workflow search with reranking and optional JSON output.

Usage:
  python query.py "slack AI chatbot with RAG"
  python query.py "webhook to postgres" -n 5 --json
  python query.py "error handling" --no-rerank
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
OVERFETCH = 4


def search_workflows(query: str, n_results: int = 3, show_json: bool = False, rerank: bool = True):
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    print(f"Searching {collection.count()} workflows for: \"{query}\"\n")

    embedding = vo.embed([query], model="voyage-code-3", input_type="query").embeddings[0]
    fetch_n = n_results * OVERFETCH if rerank else n_results
    results = collection.query(query_embeddings=[embedding], n_results=fetch_n, include=["documents", "metadatas", "distances"])

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    scores = [max(0, 1 - d) for d in results["distances"][0]]

    if rerank and documents:
        try:
            rr = vo.rerank(query=query, documents=documents, model="rerank-2.5-lite", top_k=n_results, truncation=True)
            reranked = [(rr_item.index, rr_item.relevance_score) for rr_item in rr.results]
            ids = [ids[idx] for idx, _ in reranked]
            documents = [documents[idx] for idx, _ in reranked]
            metadatas = [metadatas[idx] for idx, _ in reranked]
            scores = [s for _, s in reranked]
            print(f"(reranked {fetch_n} -> {len(ids)} results)\n")
        except Exception as e:
            print(f"[WARNING] Rerank failed: {e}\n")
            ids, documents, metadatas, scores = ids[:n_results], documents[:n_results], metadatas[:n_results], scores[:n_results]

    for i in range(len(ids)):
        meta = metadatas[i]
        print(f"{'=' * 60}")
        print(f"Match {i + 1} (score: {scores[i]:.3f})")
        print(f"Name: {meta.get('name', 'unknown')}")
        print(f"Source: {meta.get('source', 'unknown')}")
        print(f"Nodes: {meta.get('node_count', '?')}")
        json_path = meta.get("json_path", "")
        if json_path:
            print(f"JSON: {json_path}")
        print(f"\nSummary:\n{documents[i]}")

        if show_json and json_path and os.path.exists(json_path):
            from clean_workflow import clean_file
            cleaned = clean_file(json_path)
            cleaned_str = json.dumps(cleaned, indent=2, ensure_ascii=False)
            print(f"\nCleaned JSON ({len(cleaned_str)} chars):")
            print(cleaned_str[:3000])
            if len(cleaned_str) > 3000:
                print("... (truncated)")
        print()


def main():
    if not VOYAGE_API_KEY:
        print("[ERROR] VOYAGE_API_KEY not set in .env")
        sys.exit(1)

    args = sys.argv[1:]
    show_json = "--json" in args
    if show_json: args.remove("--json")
    no_rerank = "--no-rerank" in args
    if no_rerank: args.remove("--no-rerank")

    n_results = 3
    for i, arg in enumerate(args):
        if arg == "-n" and i + 1 < len(args):
            n_results = int(args[i + 1])
            args = args[:i] + args[i + 2:]
            break

    query = " ".join(args) if args else input("Describe the workflow: ")
    search_workflows(query, n_results=n_results, show_json=show_json, rerank=not no_rerank)


if __name__ == "__main__":
    main()
