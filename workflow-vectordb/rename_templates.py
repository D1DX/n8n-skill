"""Rename template JSONs from {id}.json to {id}_{Sanitized_Name}.json."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "repos", "n8n-templates")


def sanitize_name(name: str, max_len: int = 80) -> str:
    name = name.encode("ascii", errors="ignore").decode().strip()
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name[:max_len].rstrip("_") if len(name) > max_len else name


def main():
    if not os.path.exists(TEMPLATES_DIR):
        print(f"[ERROR] Directory not found: {TEMPLATES_DIR}")
        sys.exit(1)

    files = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".json") and not f.startswith("_")]
    renamed = errors = 0

    for fname in files:
        stem = fname[:-5]
        if not stem.isdigit():
            continue
        try:
            with open(os.path.join(TEMPLATES_DIR, fname), encoding="utf-8-sig") as f:
                raw = json.load(f)
            outer = raw.get("workflow", raw)
            name = outer.get("name", "") or (outer.get("workflow", {}).get("name", ""))
            safe = sanitize_name(name)
            if not safe:
                continue
            os.rename(os.path.join(TEMPLATES_DIR, fname), os.path.join(TEMPLATES_DIR, f"{stem}_{safe}.json"))
            renamed += 1
        except Exception:
            errors += 1
        if renamed % 500 == 0 and renamed > 0:
            print(f"  {renamed} renamed...")

    print(f"[OK] {renamed} renamed, {errors} errors")


if __name__ == "__main__":
    main()
