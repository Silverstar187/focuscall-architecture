# Tech Stack and Capacity Planning

> Related: [Per-Tenant Architecture](02-per-tenant-architecture.md) | [ZeroClaw Reference](07-zeroclaw-reference.md) | [Provisioning Flow](05-provisioning-flow.md) | [README](README.md)

---

## Full Stack Table

| Component | Technology | Version | Role |
|-----------|-----------|---------|------|
| AI Agent Runtime | ZeroClaw (b0xtch fork) | 0.6.7 | Per-user AI agent process; Handles message routing, LLM calls, tool execution, multi-personality (Hands) |
| Knowledge Graph | SurrealDB (embedded) | 3.0+ | Per-user embedded graph + vector + relational database; No server process needed |
| Ontology Layer | Turtle/RDF (.ttl files) | W3C standard | Domain knowledge models; Defines entity types, relations, and ADHS/health/finance concepts |
| Process Manager | systemd (template units) | OS default | Manages per-user ZeroClaw processes via `focuscall@.service` template |
| Auth + DB | Supabase | Latest | User authentication (JWT), user data storage, Edge Functions, Row-Level Security |
| Edge Functions | Deno (Supabase) | Built-in | Serverless function runtime for provisioning triggers and webhooks |
| Reverse Proxy | nginx | 1.25+ | Routes browser/API traffic to correct per-user ZeroClaw port; TLS termination |
| Webhook Listener | Python (http.server) or Node.js | 3.11 / 20 | Lightweight HTTP server on VPS receiving provisioning calls from Supabase |
| Frontend | React + Vite + Tailwind | React 18 | Web dashboard for account management, goal overview, chat history |
| Container Runtime | Docker Compose | 2.x | Runs Supabase stack locally / on VPS for self-hosted deployment |
| Server | Hetzner CAX21 (ARM64) | — | Primary VPS; all components run here |
| Messaging Channels | Telegram, WhatsApp, etc. | — | User-facing interfaces; ZeroClaw handles protocol adapters |
| LLM Providers | OpenAI, Anthropic (user-supplied) | Per user | LLM inference; each user provides their own API key |

---

## Server Specifications: Hetzner CAX21

| Spec | Value |
|------|-------|
| Provider | Hetzner Cloud |
| Server type | CAX21 |
| CPU | 4 vCPU (ARM64 / Ampere Altra) |
| RAM | 8 GB |
| Disk | 80 GB NVMe SSD |
| Network | 20 TB/month included |
| Price | 6.60 EUR/month |
| Architecture | ARM64 (aarch64) |
| OS | Ubuntu 24.04 LTS (ARM) |

**Why ARM64 (CAX series):**
- Significantly cheaper than x86 Hetzner instances at the same RAM/CPU tier
- ZeroClaw distributes ARM64 binaries
- SurrealDB has ARM64 builds
- No performance penalty for this workload (no AVX-intensive inference — that runs on the user's LLM provider)

---

## Capacity Math

### ZeroClaw Memory Profile

| State | RAM Usage |
|-------|----------|
| Idle (no active conversation) | ~3–5 MB |
| Active conversation | ~8–15 MB peak |
| With SurrealDB embedded | +2–5 MB per instance |
| Total per active instance | ~10–20 MB |
| Total per idle instance | ~5–10 MB |

### Theoretical Maximum (RAM-bound)

```
Available RAM for instances:
  8 GB total
  - 512 MB OS + kernel
  - 512 MB nginx
  - 512 MB Supabase stack (Postgres, Auth, Storage, etc.)
  - 256 MB webhook listener + misc
  ─────────────────────────────────────
  ~6.2 GB available for ZeroClaw instances

Theoretical max (all idle at 5 MB):  6200 MB / 5 MB = ~1240 instances
Practical max (mixed idle/active):    6200 MB / 10 MB = ~620 instances
Conservative estimate (headroom):     ~500 instances
```

### CPU-Bound Check

Each ZeroClaw instance at idle uses <0.1% CPU. Active (during LLM call): ~0.5% CPU (the heavy lifting is done by the remote LLM API, not the VPS).

```
4 vCPU × 100% = 400 CPU units available
- OS/nginx/Supabase: ~20 CPU units
- 500 instances × 0.5% peak: 250 CPU units
Remaining headroom: ~130 CPU units
```

RAM is the binding constraint, not CPU.

### Storage

```
Per user:
  - config.toml:  ~1 KB
  - db/ (SurrealDB, 6 months of use): ~50–200 MB
  - logs/ (rotated weekly): ~5–10 MB
  - files/: varies (assume ~20 MB average)

Total per user: ~100–250 MB
80 GB disk:
  - OS + Supabase + ZeroClaw binary + ontologies: ~10 GB
  - Available for user data: ~70 GB
  - At 200 MB/user: 70 GB / 200 MB = 350 users

Storage limit at 350 users → add second disk or object storage for `files/`
```

---

## Scaling Path

### Phase 1: Single Server (0–300 users)

Everything runs on one CAX21. No changes needed.

### Phase 2: Storage Expansion (300–500 users)

Add Hetzner Volume (additional block storage) mounted at `/opt/focuscall/users/`. Separate user data from OS disk.

Cost addition: ~0.05 EUR/GB/month → 100 GB extra = 5 EUR/month.

### Phase 3: Second Server (500–1000 users)

Add a second CAX21 (6.60 EUR/mo). Distribute users across servers:
- Server 1: users with uid ending 0–7
- Server 2: users with uid ending 8–f

nginx on Server 1 routes to Server 2 for its users. The registry.json gains a `server` field per instance.

### Phase 4: Load Balancer (1000+ users)

Add Hetzner Load Balancer (6 EUR/mo). Multiple CAX21 application servers behind it. Supabase (already external) handles auth.

---

## Cost Projection Table

| Active Users | Servers | Storage | Supabase | LLM (n/a) | Total/month | Per-User Cost |
|-------------|---------|---------|----------|-----------|-------------|---------------|
| 10 | 1× CAX21 (6.60) | — | Free tier | — | ~7 EUR | ~0.70 EUR |
| 50 | 1× CAX21 (6.60) | — | Free tier | — | ~7 EUR | ~0.14 EUR |
| 100 | 1× CAX21 (6.60) | +20 GB vol (1.00) | Pro (25 EUR) | — | ~33 EUR | ~0.33 EUR |
| 300 | 1× CAX21 (6.60) | +80 GB vol (4.00) | Pro (25 EUR) | — | ~36 EUR | ~0.12 EUR |
| 500 | 2× CAX21 (13.20) | 2× 80 GB vol (8.00) | Pro (25 EUR) | — | ~46 EUR | ~0.09 EUR |
| 1000 | 4× CAX21 (26.40) | 4× 80 GB vol (16.00) | Pro (25 EUR) | — | ~67 EUR | ~0.07 EUR |

Note: LLM costs are paid by users directly via their own API keys — the platform has zero LLM infrastructure cost.

### Revenue Model Implications

At 500 users paying 5 EUR/month:
- Revenue: 2,500 EUR/month
- Infrastructure: ~46 EUR/month
- Infrastructure margin: ~98%

The economics are exceptional because the platform bears zero LLM cost and uses ultra-efficient ARM64 containers.

---

## Disk Layout Summary

```
/
├── opt/
│   └── focuscall/              ← Main application root
│       ├── users/              ← Per-user instance data (consider separate volume)
│       ├── ontologies/         ← Shared .ttl files (~500 KB total)
│       ├── registry.json       ← Port/user mapping
│       ├── provision.sh        ← Provisioning script
│       └── logs/               ← System-level logs
├── usr/local/bin/
│   └── zeroclaw                ← ZeroClaw binary (8.8 MB)
├── etc/systemd/system/
│   └── focuscall@.service      ← Template unit file
└── var/
    └── www/focuscall/          ← Frontend static files (served by nginx)
```
