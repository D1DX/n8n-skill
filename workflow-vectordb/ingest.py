"""Ingest n8n workflow JSONs into ChromaDB.

Embeddings provider is selected via EMBEDDINGS_PROVIDER env var
(voyage default, openai alternative). See embeddings.py for details.

Two modes:
  1. From workflow JSON files (repos/ directory):
     python ingest.py

  2. From pre-built summaries (no repos needed):
     python ingest.py --from-summaries summaries.jsonl

Mode 2 skips JSON parsing and uses pre-extracted summaries.
"""
import json
import os
import sys
import glob
import hashlib
import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv

load_dotenv()

import embeddings as embeddings_mod  # noqa: E402  (after load_dotenv so env vars are visible)

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "n8n_workflows"
BATCH_SIZE = 64
BATCH_DELAY_SEC = 0.5

# Workflow sources (relative paths)
REPOS = {
    "danitilahun": "repos/danitilahun/workflows",
    "enescingoz": "repos/enescingoz",
}
TEMPLATES_DIR = "repos/n8n-templates"


def _unwrap_workflow(raw: dict) -> tuple[dict, dict]:
    """Unwrap workflow JSON to (importable_wf, metadata)."""
    meta = {}
    wf = raw

    if "workflow" in wf:
        outer = wf["workflow"]
        if isinstance(outer, dict) and "workflow" in outer and isinstance(outer["workflow"], dict):
            inner = outer["workflow"]
            if "nodes" in inner:
                meta = {
                    "name": outer.get("name"),
                    "description": outer.get("description"),
                    "categories": [c.get("name") for c in outer.get("categories", []) if c.get("name")],
                }
                return inner, meta
        if isinstance(outer, dict) and "nodes" in outer:
            return outer, meta

    return wf, meta


def strip_prefix(node_type: str) -> str:
    for prefix in ("n8n-nodes-base.", "@n8n/n8n-nodes-langchain.", "n8n-nodes-"):
        if node_type.startswith(prefix):
            return node_type[len(prefix):]
    return node_type


def find_triggers(nodes: list) -> list[str]:
    triggers = []
    for n in nodes:
        ntype = n.get("type", "").lower()
        if any(kw in ntype for kw in ("trigger", "webhook", "cron", "schedule")):
            triggers.append(n.get("name", strip_prefix(n.get("type", "?"))))
    return triggers


def extract_services(nodes: list) -> list[str]:
    services = set()
    skip = {"manualTrigger", "scheduleTrigger", "stickyNote", "noOp",
            "set", "code", "if", "switch", "merge", "splitOut",
            "splitInBatches", "aggregate", "filter", "sort",
            "removeDuplicates", "limit", "itemLists", "markdown",
            "respondToWebhook", "executeWorkflow", "errorTrigger",
            "stopAndError", "wait", "start", "functionItem", "function",
            "writeBinaryFile", "readBinaryFile", "moveBinaryData",
            "compression", "crypto", "dateTime", "xml", "html",
            "htmlExtract", "executeCommand", "editImage", "convertToFile",
            "extractFromFile", "noop"}
    for n in nodes:
        short = strip_prefix(n.get("type", ""))
        svc = short.replace("Trigger", "").replace("trigger", "")
        if svc.lower() not in {s.lower() for s in skip} and svc:
            services.add(svc)
    return sorted(services)


def build_flow_chain(nodes: list, connections: dict) -> str:
    if not connections or not nodes:
        return ""

    targets = set()
    for src, conns in connections.items():
        for output_group in conns.get("main", []):
            if not output_group:
                continue
            for link in output_group:
                if not link or not isinstance(link, dict):
                    continue
                targets.add(link.get("node", ""))

    trigger_names = [n.get("name") for n in nodes
                     if any(kw in n.get("type", "").lower()
                            for kw in ("trigger", "webhook", "cron", "schedule"))]
    starts = trigger_names or [n.get("name") for n in nodes
                                if n.get("name") not in targets
                                and n.get("type", "") != "n8n-nodes-base.stickyNote"]
    if not starts:
        return ""

    chain = []
    visited = set()
    current = starts[0]
    while current and len(chain) < 15:
        if current in visited:
            chain.append(f"{current} (loop)")
            break
        visited.add(current)
        chain.append(current)
        conns = connections.get(current, {}).get("main", [])
        next_node = None
        for output_group in conns:
            if not output_group:
                continue
            for link in output_group:
                if not link or not isinstance(link, dict):
                    continue
                candidate = link.get("node", "")
                if candidate and candidate not in visited:
                    next_node = candidate
                    break
            if next_node:
                break
        current = next_node

    return " -> ".join(chain)


def extract_llm_prompts(nodes: list) -> list[str]:
    prompts = []
    prompt_keys = ("text", "systemMessage", "messages", "prompt", "instructions")
    agent_types = ("agent", "chainllm", "lmchat", "openai", "anthropic", "gemini", "ollama")
    for n in nodes:
        ntype = n.get("type", "").lower()
        if not any(at in ntype for at in agent_types):
            continue
        params = n.get("parameters", {})
        for key in prompt_keys:
            val = params.get(key)
            if not val:
                continue
            if isinstance(val, dict) and "values" in val:
                for msg in val.get("values", []):
                    content = msg.get("message", "")
                    if content and len(content) > 20:
                        prompts.append(content[:300])
            elif isinstance(val, str) and len(val) > 20:
                prompts.append(val[:300])
    return prompts


def extract_api_endpoints(nodes: list) -> list[str]:
    urls = []
    for n in nodes:
        ntype = n.get("type", "").lower()
        if "httprequest" not in ntype and "http" not in n.get("name", "").lower():
            continue
        url = n.get("parameters", {}).get("url", "")
        if url and not url.startswith("="):
            clean = url.split("?")[0]
            if clean and len(clean) > 8:
                urls.append(clean)
    return list(set(urls))


def extract_summary(wf: dict, filename: str, source: str) -> str:
    name = wf.get("name") or Path(filename).stem.replace("_", " ")
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    real_nodes = [n for n in nodes if "stickyNote" not in n.get("type", "")]
    unique_types = sorted(set(strip_prefix(n.get("type", "?")) for n in real_nodes))
    triggers = find_triggers(nodes)
    services = extract_services(nodes)
    flow = build_flow_chain(nodes, connections)
    error_handling = []
    for n in nodes:
        if "errortrigger" in n.get("type", "").lower():
            error_handling.append("error trigger")
        if n.get("parameters", {}).get("continueOnFail"):
            error_handling.append(f"continueOnFail on {n.get('name', '?')}")
    prompts = extract_llm_prompts(nodes)
    api_urls = extract_api_endpoints(nodes)
    categories = wf.get("_categories", [])
    description = wf.get("description", "")

    lines = [f"Name: {name}"]
    if description:
        lines.append(f"Description: {description}")
    if categories:
        lines.append(f"Categories: {', '.join(categories)}")
    lines.append(f"Trigger: {', '.join(triggers) if triggers else 'manual/unknown'}")
    lines.append(f"Nodes ({len(real_nodes)}): {', '.join(unique_types)}")
    if flow:
        lines.append(f"Flow: {flow}")
    if services:
        lines.append(f"Services: {', '.join(services)}")
    if prompts:
        lines.append(f"LLM Prompts: {' | '.join(prompts[:3])}")
    if api_urls:
        lines.append(f"API Endpoints: {', '.join(api_urls[:5])}")
    lines.append(f"Error handling: {', '.join(error_handling) if error_handling else 'none'}")
    return "\n".join(lines)


def load_from_summaries(path: str) -> list[dict]:
    """Load pre-built summaries from JSONL file."""
    workflows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            workflows.append({
                "id": entry["id"],
                "summary": entry["summary"],
                "json_path": "",
                "source": entry.get("source", "unknown"),
                "name": entry.get("name", "unknown"),
                "node_count": entry.get("node_count", 0),
            })
    return workflows


def load_from_repos() -> list[dict]:
    """Load workflows from JSON files in repos/ directory."""
    workflows = []
    seen = set()

    def _process_file(fp, source):
        try:
            with open(fp, encoding="utf-8-sig") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        wf, meta = _unwrap_workflow(raw)
        nodes = wf.get("nodes", [])
        if not nodes:
            return
        name = meta.get("name") or wf.get("name") or Path(fp).stem
        dedup_key = f"{name}|{len(nodes)}"
        if dedup_key in seen:
            return
        seen.add(dedup_key)
        if meta.get("description") and not wf.get("description"):
            wf["description"] = meta["description"]
        if meta.get("categories"):
            wf["_categories"] = meta["categories"]
        summary = extract_summary(wf, fp, source)
        workflows.append({
            "id": hashlib.md5(fp.encode()).hexdigest()[:12],
            "summary": summary,
            "json_path": os.path.abspath(fp),
            "source": source,
            "name": name,
            "node_count": len(nodes),
        })

    for source, base_path in REPOS.items():
        if not os.path.exists(base_path):
            print(f"[WARNING] Repo not found: {base_path}, skipping")
            continue
        pattern = os.path.join(base_path, "**", "*.json") if source != "danitilahun" else os.path.join(base_path, "*.json")
        files = glob.glob(pattern, recursive=True)
        print(f"[OK] {source}: found {len(files)} JSON files")
        for fp in files:
            _process_file(fp, source)

    if os.path.exists(TEMPLATES_DIR):
        files = glob.glob(os.path.join(TEMPLATES_DIR, "*.json"))
        print(f"[OK] n8n-templates: found {len(files)} JSON files")
        for fp in files:
            _process_file(fp, "n8n-templates")
    else:
        print(f"[WARNING] Templates dir not found: {TEMPLATES_DIR}, skipping")

    return workflows


def main():
    print("=== n8n Workflow Ingestion ===\n")

    # Check for --from-summaries mode
    if "--from-summaries" in sys.argv:
        idx = sys.argv.index("--from-summaries")
        path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "summaries.jsonl"
        print(f"Loading from summaries: {path}")
        workflows = load_from_summaries(path)
    else:
        workflows = load_from_repos()

    print(f"\n[OK] Total unique workflows: {len(workflows)}")
    if not workflows:
        print("[ERROR] No workflows found.")
        sys.exit(1)

    # Embed
    provider = embeddings_mod.get()
    print(f"\nEmbedding {len(workflows)} summaries with {embeddings_mod.describe()}...")
    all_embeddings = []
    total_batches = (len(workflows) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(workflows), BATCH_SIZE):
        batch = workflows[i:i + BATCH_SIZE]
        summaries = [w["summary"] for w in batch]
        try:
            all_embeddings.extend(provider.embed_documents(summaries))
        except Exception as e:
            print(f"  [ERROR] Batch failed: {e}, retrying in 5s...")
            time.sleep(5)
            all_embeddings.extend(provider.embed_documents(summaries))
        done = min(i + BATCH_SIZE, len(workflows))
        batch_num = (i // BATCH_SIZE) + 1
        print(f"  Batch {batch_num}/{total_batches} - {done}/{len(workflows)}")
        if i + BATCH_SIZE < len(workflows):
            time.sleep(BATCH_DELAY_SEC)

    print(f"[OK] All embeddings complete ({len(all_embeddings)} vectors)")

    # Store
    print(f"\nStoring in ChromaDB at {CHROMA_PATH}...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    for i in range(0, len(workflows), 500):
        batch = workflows[i:i + 500]
        batch_embeddings = all_embeddings[i:i + 500]
        collection.add(
            ids=[w["id"] for w in batch],
            documents=[w["summary"] for w in batch],
            embeddings=batch_embeddings,
            metadatas=[{"json_path": w["json_path"], "source": w["source"], "name": w["name"], "node_count": w["node_count"]} for w in batch],
        )
        print(f"  Stored {min(i + 500, len(workflows))}/{len(workflows)}")

    print(f"\n[SUCCESS] Ingestion complete!")
    print(f"  Workflows indexed: {collection.count()}")


if __name__ == "__main__":
    main()
