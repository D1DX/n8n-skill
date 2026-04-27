# Workflow Vector DB

*Contributed by Asaf Lecht ([@Seithx](https://github.com/Seithx))*

**Don't build n8n workflows from scratch.** Search 6,902 real workflows by describing what you need, find the closest match, study its structure, and use it as your starting point.

```bash
python search.py "webhook receives form data, validates it, writes to postgres"
```

```
1. [0.629] Validate JSON and CSV import data via webhook (9 nodes, n8n-templates)
   repos/n8n-templates/13999_Validate_JSON_and_CSV_import_data_via_webhook.json
2. [0.594] Postgres Webhook Automation (19 nodes, danitilahun)
   repos/danitilahun/workflows/1249_Postgres_Webhook_Automation_Webhook.json
3. [0.574] Postgres Webhook Create (19 nodes, danitilahun)
   repos/danitilahun/workflows/0666_Postgres_Webhook_Create_Webhook.json
```

Open the matched JSON, see exactly which nodes were used, how they connect, what expressions they use -- then adapt it for your case.

---

## Setup

### Quick Start (from pre-built summaries, ~2 minutes)

Uses the included `summaries.jsonl` so you don't need to download 7K workflow files. You get search but can't read the matched workflow JSON.

```bash
cd workflow-vectordb
pip install chromadb voyageai python-dotenv
cp .env.example .env   # add your VOYAGE_API_KEY (free from https://dash.voyageai.com/)
python ingest.py --from-summaries summaries.jsonl
python search.py "what you want to build"
```

### Full Setup (with downloadable workflow JSONs, ~90 minutes)

Downloads the actual workflow files so you can read the full JSON after matching.

```bash
cd workflow-vectordb
pip install chromadb voyageai python-dotenv
cp .env.example .env   # add your VOYAGE_API_KEY

# Clone community repos
git clone https://github.com/Danitilahun/n8n-workflow-templates repos/danitilahun
git clone https://github.com/enescingoz/awesome-n8n-templates repos/enescingoz

# Download official n8n.io templates (~45 min, safe to restart)
powershell -ExecutionPolicy Bypass -File download_templates.ps1

# Optional: rename to descriptive filenames
python rename_templates.py

# Build vector DB
python ingest.py

# Search
python search.py "describe what you want to build"
```

---

## Scripts

| Script | What it does | When to use |
|---|---|---|
| `search.py` | Compact search. 3 lines per match: name, score, path. | Quick lookup. Works from terminal or called by AI assistants. |
| `query.py` | Full search. Shows complete summary per match. | When you want to see trigger types, node lists, flow chains, LLM prompts. |
| `query.py --json` | Same as above + shows the cleaned workflow JSON. | When you want to study the actual node configuration. |
| `ingest.py` | Builds the ChromaDB vector database from workflow JSONs. | Run once after setup, or re-run to update. |
| `ingest.py --from-summaries` | Builds ChromaDB from `summaries.jsonl` (no JSONs needed). | Quick start without downloading 7K files. |
| `clean_workflow.py` | Strips noise from workflow JSONs (icons, codex, positions). ~57% smaller. | When passing workflow JSON to an LLM or reviewing manually. |
| `download_templates.ps1` | Downloads ~4,800 official n8n.io templates. Checkpoint-safe. | One-time setup. PowerShell (Windows). |
| `rename_templates.py` | Renames `{id}.json` to `{id}_{Name}.json` for browsability. | After downloading templates. |

All scripts work standalone from the terminal. No AI assistant or special tooling required.

---

## What's in a Summary

Each workflow gets a text summary (~60-200 tokens) that captures what it does. This is what gets embedded and searched against. Example:

```
Name: Slack AI Chatbot with RAG for company staff
Trigger: Get message, When clicking 'Test workflow'
Nodes (17): agent, documentDefaultDataLoader, embeddingsOpenAi, googleDrive,
  httpRequest, lmChatAnthropic, manualTrigger, memoryBufferWindow, slack,
  slackTrigger, textSplitterTokenSplitter, toolCalculator, vectorStoreQdrant
Flow: Get message -> AI Agent -> Send message
Services: googleDrive, httpRequest, lmChatAnthropic, slack, vectorStoreQdrant
LLM Prompts: ={{ $json.blocks[0].elements[0].elements[1].text }}
API Endpoints: https://QDRANTURL/collections/COLLECTION
Error handling: none
```

Fields extracted per workflow:
- **Name** and **Description** (from JSON metadata or n8n template API)
- **Categories** (e.g. "AI Chatbot", "Lead Generation")
- **Trigger** (schedule, webhook, manual, form, event)
- **Node types** (deduplicated, prefix-stripped)
- **Flow chain** (simplified: nodeA -> nodeB -> nodeC)
- **Services** (external integrations: Slack, Postgres, OpenAI, etc.)
- **LLM Prompts** (system/user prompts from Agent/LLM nodes, first 300 chars)
- **API Endpoints** (URLs from HTTP Request nodes)
- **Error handling** (error triggers, continueOnFail flags)

---

## How It Works

```
[6,902 workflow JSONs from 3 sources]
        |
[Extract text summaries per workflow]
        |
[Embed with Voyage AI voyage-code-3]
        |
[Store in local ChromaDB (cosine similarity)]

--- at query time ---

[Your description: "slack chatbot with RAG"]
        |
[Embed query with voyage-code-3]
        |
[Vector search: fetch top 12 candidates]
        |
[Rerank with Voyage rerank-2.5-lite: return top 3]
        |
[Display: name, score, node count, JSON path]
```

The reranking step overfetches 4x results from the vector search, then uses a cross-encoder model to compare each candidate against your query more carefully. This promotes the most semantically relevant matches and pushes down false positives.

## Sources

| Source | Count | Description |
|---|---|---|
| [Danitilahun/n8n-workflow-templates](https://github.com/Danitilahun/n8n-workflow-templates) | ~2,053 | Community workflows |
| [enescingoz/awesome-n8n-templates](https://github.com/enescingoz/awesome-n8n-templates) | ~299 | Categorized community workflows |
| [n8n.io template API](https://api.n8n.io/api/templates/search) | ~4,800 | Official n8n templates with rich descriptions |

## Search Quality

Tested across 15 diverse queries with reranking enabled:

| Query | Score | Top Match |
|---|---|---|
| AI classify support tickets | 0.91 | Production AI Playbook + Zoho Desk classifier |
| YouTube transcript summarize | 0.74 | YouTube Video Summarizer |
| WhatsApp chatbot with OpenAI | 0.72 | Building Your First WhatsApp Chatbot |
| Gmail attachments to Drive | 0.70 | Attachments Gmail to Drive and Sheets |
| Backup database to S3 | 0.70 | Scheduled Backup Automation |
| Slack AI agent + doc search | 0.68 | Slack AI Chatbot with RAG |
| Jira from Slack command | 0.66 | Create a new issue in Jira |
| RSS feed to Discord | 0.61 | RSS AI Summarizer |

## Dependencies

- **chromadb** -- Local vector database. No server, no Docker. Stores everything in a `chroma_db/` folder.
- **voyageai** -- Embedding (`voyage-code-3`) and reranking (`rerank-2.5-lite`). Free tier: 200M tokens. Full DB uses ~2M tokens.
- **python-dotenv** -- Load API key from `.env` file.

## Files

```
workflow-vectordb/
  .env.example          # VOYAGE_API_KEY placeholder
  .gitignore            # Excludes .env, chroma_db/, repos/
  REFERENCE.md          # This file
  requirements.txt      # Python dependencies
  summaries.jsonl       # 6,902 pre-extracted summaries (21MB)
  ingest.py             # Build ChromaDB (from repos or from summaries)
  search.py             # Compact search (terminal or AI assistant)
  query.py              # Full search with --json and reranking
  clean_workflow.py     # Strip noise from workflow JSONs
  download_templates.ps1  # Download n8n.io templates (Windows PowerShell)
  rename_templates.py   # Rename {id}.json to descriptive names
```
