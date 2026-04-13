"""Clean n8n workflow JSONs by stripping noise fields.

Removes base64 icons, codex documentation, UI positions, credentials,
user metadata -- fields useless for LLM consumption. ~57% size reduction.

Usage:
  from clean_workflow import clean_file
  cleaned = clean_file("path/to/workflow.json")
"""
import json
import os
import sys
import glob
from pathlib import Path


def clean_template(raw: dict) -> dict:
    """Clean an API template JSON."""
    outer = raw.get("workflow", raw)

    cleaned = {
        "id": outer.get("id"),
        "name": outer.get("name"),
        "description": outer.get("description"),
        "categories": [c.get("name") for c in outer.get("categories", []) if c.get("name")],
        "createdAt": outer.get("createdAt"),
    }

    inner = outer.get("workflow", {})
    if inner and "nodes" in inner:
        cleaned["workflow"] = clean_workflow_nodes(inner)
    elif "nodes" in outer:
        cleaned["workflow"] = clean_workflow_nodes(outer)

    return cleaned


def clean_workflow_nodes(wf: dict) -> dict:
    """Clean an importable workflow JSON (nodes + connections)."""
    cleaned_nodes = []
    for node in wf.get("nodes", []):
        ntype = node.get("type", "")
        if "stickyNote" in ntype:
            continue

        cleaned_node = {
            "name": node.get("name"),
            "type": ntype,
            "typeVersion": node.get("typeVersion"),
        }

        params = node.get("parameters", {})
        if params:
            cleaned_params = _clean_params(params)
            if cleaned_params:
                cleaned_node["parameters"] = cleaned_params

        cleaned_nodes.append(cleaned_node)

    return {
        "nodes": cleaned_nodes,
        "connections": wf.get("connections", {}),
        "settings": wf.get("settings"),
    }


def _clean_params(params: dict, depth: int = 0) -> dict:
    """Recursively clean node parameters."""
    if depth > 5:
        return params

    cleaned = {}
    for k, v in params.items():
        if k == "additionalFields":
            if isinstance(v, dict) and v:
                inner = _clean_params(v, depth + 1)
                if inner:
                    cleaned[k] = inner
            continue
        if v is None or v == "" or v == [] or v == {}:
            continue
        if isinstance(v, str) and (v.startswith("data:") or len(v) > 5000):
            continue
        if isinstance(v, dict):
            inner = _clean_params(v, depth + 1)
            if inner:
                cleaned[k] = inner
        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if isinstance(item, dict):
                    inner = _clean_params(item, depth + 1)
                    if inner:
                        cleaned_list.append(inner)
                else:
                    cleaned_list.append(item)
            if cleaned_list:
                cleaned[k] = cleaned_list
        else:
            cleaned[k] = v

    return cleaned


def clean_file(input_path: str, output_path: str = None) -> dict:
    """Clean a single workflow JSON file."""
    with open(input_path, encoding="utf-8-sig") as f:
        raw = json.load(f)

    cleaned = clean_template(raw)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)

    return cleaned
