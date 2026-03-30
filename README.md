# n8n Skill for Claude Code

[![Author](https://img.shields.io/badge/Author-Daniel_Rudaev-000000?style=flat)](https://github.com/daniel-rudaev)
[![Studio](https://img.shields.io/badge/Studio-D1DX-000000?style=flat)](https://d1dx.com)
[![n8n](https://img.shields.io/badge/n8n-Skill-EA4B71?style=flat&logo=n8n&logoColor=white)](https://n8n.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](./LICENSE)

Complete n8n skill for Claude Code. 9 domains covering workflow building, node configuration, code nodes, expression syntax, validation, MCP tools, credentials, administration, and data tables. Built from n8n source code and production workflows at [D1DX](https://d1dx.com).

Extends [czlonkowski/n8n-skills](https://github.com/czlonkowski/n8n-skills) with source-code-verified credential management, internal API reference, data tables, folder management, and a unified entry point.

## What's Included

| Domain | Source | What it covers |
|--------|--------|---------------|
| Workflow Patterns | czlonkowski | 5 architectural patterns — webhook, HTTP API, database, AI agent, scheduled |
| Node Configuration | czlonkowski | Operation-aware config, property dependencies, required fields |
| Code — JavaScript | czlonkowski | `$input/$json/$node` syntax, `$helpers.httpRequest()`, DateTime, error patterns |
| Code — Python | czlonkowski | `_input/_json` syntax, standard library, limitations |
| Expression Syntax | czlonkowski | `{{ }}` expressions, `$json/$node` variables, common mistakes |
| Validation | czlonkowski | Validation errors/warnings, false positives, profiles |
| MCP Tools | czlonkowski | Tool selection, parameter formats, workflow management patterns |
| **Credentials** | D1DX | Type discovery, credential testing (3 strategies), OAuth1/OAuth2 flows, httpCustomAuth, `isPartialData` updates |
| **Administration** | D1DX | Data tables (full CRUD + CSV), folder management, community packages, Docker deployment, CLI commands, backup/restore |

## Install

### Claude Code (CLI or IDE)

Copy the skill folder to your Claude Code skills directory:

```bash
# Clone with submodule
git clone --recursive https://github.com/D1DX/n8n-skill.git

# Copy to Claude Code skills
cp -r n8n-skill ~/.claude/skills/n8n
```

Or add as a git submodule in your own skills repo:

```bash
git submodule add https://github.com/D1DX/n8n-skill.git path/to/skills/n8n
```

### Verify

Start a new Claude Code session. The skill should appear in the skill list as `n8n`. Test with `/n8n` or ask any n8n-related question.

## Recommended: n8n MCP Server

This skill works standalone but is designed to pair with an n8n MCP server for full workflow management. The skill provides knowledge; the MCP provides live instance access.

Compatible MCP servers:

| MCP Server | What it adds |
|-----------|-------------|
| [czlonkowski/n8n-mcp](https://github.com/czlonkowski/n8n-mcp) | Node search, validation, smart workflow updates, template deployment |
| [leonardsellem/n8n-mcp-server](https://github.com/leonardsellem/n8n-mcp-server) | Workflow CRUD, execution management |

## Structure

```
n8n-skill/
├── SKILL.md              — Unified entry point (auto-triggers on n8n tasks)
├── credentials/
│   └── SKILL.md          — Credential types, testing, OAuth, httpCustomAuth
├── administration/
│   └── SKILL.md          — Data tables, folders, packages, Docker, CLI, backup
└── czlonkowski/          — Git submodule: czlonkowski/n8n-skills
    └── skills/
        ├── n8n-code-javascript/
        ├── n8n-code-python/
        ├── n8n-expression-syntax/
        ├── n8n-mcp-tools-expert/
        ├── n8n-node-configuration/
        ├── n8n-validation-expert/
        └── n8n-workflow-patterns/
```

## Method Priority

The skill teaches Claude when to use each method:

| Priority | Method | Use for |
|----------|--------|---------|
| 1 | MCP | Workflow CRUD, node search, validation, templates, executions |
| 2 | Public REST API | Credential CRUD, tags, variables, data table rows |
| 3 | Internal API | Credential testing, folders, community packages, column CRUD |
| 4 | CLI | Decrypted credential export, full database backup, migration rollback |
| 5 | Docker/Infra | Encryption key, database config, version upgrades, logs |

## Updating

The czlonkowski submodule tracks upstream. To update:

```bash
cd path/to/n8n-skill
git submodule update --remote czlonkowski
git add czlonkowski
git commit -m "chore: update n8n-skills submodule"
```

## Sources

- **Credentials and Administration:** Verified against [n8n-io/n8n](https://github.com/n8n-io/n8n) source code (`master` branch, March 2026). Controllers read: `credentials.controller.ts`, `credentials-tester.service.ts`, `data-table.controller.ts`, `folder.controller.ts`, `community-packages.controller.ts`, `oauth2-credential.controller.ts`.
- **Workflow building domains:** [czlonkowski/n8n-skills](https://github.com/czlonkowski/n8n-skills) (MIT License).

## Credits

Workflow building skills by [Maciej Czlonkowski](https://github.com/czlonkowski/n8n-skills). Credentials, administration, and unified skill by [D1DX](https://github.com/D1DX).

## License

MIT License — Copyright (c) 2026 Daniel Rudaev @ D1DX
