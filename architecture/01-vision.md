# Vision: Personal AI OS

> Related: [Per-Tenant Architecture](02-per-tenant-architecture.md) | [Multi-Agent Personalities](04-multi-agent-personalities.md) | [README](README.md)

---

## Core Concept

Every user gets their **own AI bot instance** — not a shared assistant, not a pool of agents. A single dedicated ZeroClaw process runs exclusively for one user, with its own knowledge graph, configuration, and memory.

This is fundamentally different from typical AI products where:
- A single model handles millions of users simultaneously
- Context is limited to the current conversation window
- There is no persistent memory across sessions
- Personalization is shallow (name, preferences) rather than structural

With focuscall.ai, your AI **knows you** in a structural sense — your goals, your blockers, your habits, your relationships, your domain knowledge — because all of it is stored in a private knowledge graph that the agent reads before every response.

---

## Key Differentiators

### 1. Knowledge Graph Per User

Each user has a private **SurrealDB** instance embedded on the server. Their goals, tasks, events, habits, and concepts are stored as a graph — not as conversation history, not as embeddings alone. The agent can traverse relationships: "What tasks are blocked by this goal? What habits support this health objective?"

See: [Knowledge Graph Design](03-knowledge-graph.md)

### 2. Full Memory and Context

The agent has persistent memory that accumulates over time. Every interaction, every completed task, every stated preference enriches the graph. There is no "context window reset" — the agent always has access to everything the user has shared.

### 3. Proactive Behavior

Because the agent has CRON access and understands the user's schedule and goals, it can initiate conversations: morning check-ins, habit reminders, milestone celebrations, blocker follow-ups. The user doesn't always have to start the conversation.

### 4. Domain-Specific Expert Personalities

The single agent instance can present different expert personalities depending on the topic. A user with ADHS, financial anxiety, and fitness goals doesn't get a generic assistant — they get a **ProductivityCoach**, a **FinanceAdvisor**, and a **HealthCoach**, each loaded with domain ontology context and specialized system prompts.

See: [Multi-Agent Personalities](04-multi-agent-personalities.md)

---

## Target Use Cases

### Primary: ADHS Coaching

People with ADHS struggle with executive function — starting tasks, prioritizing, managing time, maintaining habits. The AI acts as:
- An external executive function scaffold
- A task breakdown engine (big goal → concrete next steps)
- A non-judgmental accountability partner
- A habit tracking and nudging system

The system is designed to meet users where they are: Telegram, WhatsApp, Discord — channels they already use, not a new app they have to remember to open.

### Expansion Domains

| Domain | Coaching Function |
|--------|------------------|
| Health | Habits, medication, appointments, energy patterns |
| Finance | Expense tracking, goal progress, spending nudges |
| Productivity | Task management, focus sessions, review cycles |
| Relationships | Communication patterns, important dates, conflict navigation |

---

## Product Model

### User-Supplied Credentials

focuscall.ai does **not** hold LLM API keys centrally. Each user brings:
- **bot_token** — their Telegram (or other channel) bot token
- **llm_api_key** — their OpenAI, Anthropic, or other LLM provider API key

This has three advantages:
1. **Cost isolation** — each user pays for their own LLM usage
2. **Privacy** — the platform cannot read conversations (it doesn't hold the decryption keys)
3. **Model choice** — users can switch LLM providers independently

Credentials are stored encrypted in Supabase with row-level security.

### Provisioning on Demand

When a user signs up, the Supabase Edge Function triggers a webhook to the VPS, which runs `provision.sh` to create their isolated instance. The full flow is documented in [Provisioning Flow](05-provisioning-flow.md).

### Infrastructure Cost

The entire platform runs on a single **Hetzner CAX21** (4 vCPU ARM64, 8GB RAM, 6.60 EUR/mo). At 500 concurrent users, that is ~1.3 euro cents per user per month for compute.

See: [Tech Stack and Capacity Planning](06-tech-stack-and-capacity.md)

---

## What focuscall.ai Is Not

- Not a general-purpose AI assistant (ChatGPT, Claude, etc.)
- Not a task manager app (Todoist, Notion)
- Not a therapy platform (clinical mental health support)
- Not a shared-infrastructure AI product

It is the **infrastructure layer** for a deeply personal, persistent, proactive AI that lives on your preferred messaging channel.
