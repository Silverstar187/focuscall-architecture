# focuscall.ai Architecture

focuscall.ai is a **Personal AI OS** — a platform where every user runs their own isolated AI agent instance, backed by a personal knowledge graph. Instead of a shared AI assistant, each user has a fully private, context-aware AI bot that learns from their goals, habits, and conversations over time.

The system is built on **ZeroClaw** (Rust, <5MB RAM per instance), **SurrealDB** (embedded knowledge graph + vector + relational), **Turtle/RDF ontologies** (per-domain knowledge models), and **Supabase** (auth, storage, edge functions) — all self-hosted on a single ARM64 VPS.

---

## Table of Contents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Vision: Personal AI OS](01-vision.md) | Core product concept, differentiators, target use cases, business model |
| 02 | [Per-Tenant Architecture](02-per-tenant-architecture.md) | Per-user isolation model, directory layout, systemd services, port registry |
| 03 | [Knowledge Graph Design](03-knowledge-graph.md) | SurrealDB embedded, Turtle ontologies, entity/relation model, query patterns |
| 04 | [Multi-Agent Personalities](04-multi-agent-personalities.md) | ZeroClaw Hands feature, domain expert agents, routing, system prompt design |
| 05 | [Provisioning Flow](05-provisioning-flow.md) | User onboarding from landing page to running instance, provision.sh walkthrough |
| 06 | [Tech Stack and Capacity Planning](06-tech-stack-and-capacity.md) | Full stack table, server specs, capacity math, scaling path, cost projections |
| 07 | [ZeroClaw Technical Reference](07-zeroclaw-reference.md) | ZeroClaw runtime stats, channels, tools, config format, autonomy levels |

---

## Quick Architecture Overview

```
User (Telegram / WhatsApp / Web)
       │
       ▼
  nginx reverse proxy  ─────────────────────────────┐
       │                                             │
       ▼                                        Supabase
  focuscall@{user_id}                      (Auth + DB + Edge Fns)
  ZeroClaw instance  ←── config.toml            │
       │              ←── bot_token              │  provision trigger
       │              ←── llm_api_key            │
       ▼                                          │
  SurrealDB embedded                        VPS webhook listener
  /opt/focuscall/users/{user_id}/db/              │
       │                                          ▼
  Knowledge Graph                           provision.sh
  (Turtle ontologies)                       (create dirs, write config,
                                             assign port, start systemd)
```

## Key Design Principles

1. **Full isolation** — one process, one database, one filesystem per user. No shared state.
2. **Bring your own credentials** — user supplies bot_token + LLM API key. Platform stores them encrypted.
3. **Knowledge graph first** — the agent always queries the graph before responding. Memory is structural, not just embeddings.
4. **Domain expert personalities** — multiple ZeroClaw "Hands" per user, each loaded with domain ontology context.
5. **Lightweight runtime** — ZeroClaw at <5MB idle enables 500–1000 concurrent users on a single Hetzner CAX21.
