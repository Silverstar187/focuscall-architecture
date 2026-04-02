# Knowledge Graph Design

> Related: [Per-Tenant Architecture](02-per-tenant-architecture.md) | [Multi-Agent Personalities](04-multi-agent-personalities.md) | [Vision](01-vision.md) | [README](README.md)

---

## Why SurrealDB v3.0+ Embedded

SurrealDB is chosen as the knowledge graph engine for three reasons:

1. **Single binary, embedded mode** — No separate server process. Each ZeroClaw instance opens the DB directly via the Rust library. One less process, one less failure point per user.
2. **Multi-model in one database** — SurrealDB handles graph traversal, vector similarity search, and relational queries in a single query language (SurrealQL). No need for separate Neo4j + pgvector + Postgres.
3. **Rust-native** — ZeroClaw is written in Rust; SurrealDB has a first-class Rust client. Zero FFI overhead, seamless async integration.

**SurrealDB v3.0+ features used:**

| Feature | Usage |
|---------|-------|
| Graph records (`->`) | Entity relationships (Goal → Task → Habit) |
| Vector fields | Semantic similarity search over concepts |
| Full-text search | Free-text recall over notes and messages |
| Schema enforcement | Typed entity definitions prevent corrupt writes |
| Embedded mode | No server process; file-based storage via RocksDB |

---

## Turtle Ontology Approach

Rather than defining schema in code or SQL migrations, focuscall.ai uses **Turtle (.ttl) RDF ontologies** to define entity types, relations, and domain knowledge.

**Why Turtle/RDF:**
- Human-readable and LLM-readable format
- Standard W3C format — tooling and validators exist
- Can be loaded directly into the agent's system prompt as context
- Domain experts (health, finance, etc.) can contribute ontologies without coding

**Two-layer ontology model:**

```
/opt/focuscall/ontologies/          ← Shared, read-only
├── core.ttl                        ← Universal entity types (User, Goal, Task, ...)
├── health.ttl                      ← Health domain extensions
├── finance.ttl                     ← Finance domain extensions
├── productivity.ttl                ← Productivity/ADHS domain
└── relationships.ttl               ← Relationship domain

/opt/focuscall/users/{user_id}/db/  ← Per-user, mutable
└── (SurrealDB contains user-specific graph instances)
```

---

## Core Entities

### User

The central node in the graph. All other entities belong to a User. Stores: name, communication channel preferences, onboarding state, active domains, timezone.

### Goal

A desired outcome the user wants to achieve. Has a title, description, target date, status (active/completed/paused), and belongs to one or more domains. Goals are the top-level organizing construct from which Tasks are derived.

### Task

A concrete, actionable step toward a Goal. Has a title, estimated duration, due date, status (todo/in-progress/done/blocked), and a `blockedBy` relation to other Tasks or external factors.

### Event

A time-bound occurrence — calendar event, session, appointment, milestone. Has start/end times, recurrence rules, and relations to Goals or Habits it is associated with.

### Habit

A recurring behavior the user wants to establish or break. Has a frequency target (daily/weekly), streak count, completion log, and a `supports` relation to Goals.

### Resource

A document, link, tool, or reference the user finds relevant. Has a URL or file reference, summary, domain tags, and `relatedTo` relations to Goals and Concepts.

### Concept

A piece of domain knowledge or a named idea the user has shared. For example: "hyperfocus", "time-blindness", "dopamine budget". Concepts are the vocabulary nodes of the knowledge graph — other entities reference them to add semantic richness.

---

## Core Relations

| Relation | Direction | Semantics |
|----------|-----------|-----------|
| `hasGoal` | User → Goal | This goal belongs to this user |
| `hasTask` | Goal → Task | This task contributes to this goal |
| `dependsOn` | Task → Task | This task cannot start until the other is done |
| `blockedBy` | Task → Task/Concept | This task is currently blocked by something |
| `triggeredBy` | Habit → Event/Task | This habit is triggered by a specific event or task completion |
| `supportsGoal` | Habit → Goal | This habit helps achieve this goal |
| `belongsToDomain` | Goal/Concept → Domain | This entity belongs to the health/finance/productivity domain |
| `relatesTo` | Concept → Concept | Two concepts are semantically related |
| `hasContext` | Task/Event → Concept | This task has a relevant concept as context |

---

## Per-Domain Ontologies

### health.ttl

Extends core entities with health-specific types: `MedicalEvent`, `Symptom`, `Medication`, `EnergyLog`. Defines relations: `hasSymptom`, `triggersSymptom`, `managedBy` (Symptom → Medication).

### finance.ttl

Extends with: `Transaction`, `Account`, `Budget`, `FinancialGoal`. Relations: `categorizedAs`, `fundedBy`, `impacts` (Transaction → Budget).

### productivity.ttl

Extends with: `FocusSession`, `EnergyLevel`, `Distraction`, `ADHSPattern`. Relations: `consumesEnergy`, `causeDistraction`, `bestTimeFor` (Task → TimeOfDay). Specifically models ADHS-relevant patterns like hyperfocus, task-switching overhead, and activation energy.

---

## Sample Turtle Snippet: productivity.ttl

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl# .
@prefix fc:   <https://focuscall.ai/ontology/core#> .
@prefix prod: <https://focuscall.ai/ontology/productivity#> .

# ── Types ──────────────────────────────────────────────────────────────────

prod:FocusSession
    a owl:Class ;
    rdfs:subClassOf fc:Event ;
    rdfs:label "Focus Session" ;
    rdfs:comment "A deliberate, timed period of focused work on a specific task." .

prod:ADHSPattern
    a owl:Class ;
    rdfs:label "ADHS Pattern" ;
    rdfs:comment "A named cognitive or behavioral pattern characteristic of ADHS." .

prod:EnergyLevel
    a owl:Class ;
    rdfs:label "Energy Level" ;
    rdfs:comment "A time-stamped record of the user's subjective energy/focus state." .

# ── Properties ─────────────────────────────────────────────────────────────

prod:requiresActivationEnergy
    a owl:DatatypeProperty ;
    rdfs:domain fc:Task ;
    rdfs:range  xsd:integer ;
    rdfs:label "Activation Energy (1-10)" ;
    rdfs:comment "How hard it is for this user to START this task. High = harder to start." .

prod:bestFocusTime
    a owl:ObjectProperty ;
    rdfs:domain fc:Task ;
    rdfs:range  prod:TimeBlock ;
    rdfs:label "Best focus time" ;
    rdfs:comment "The time of day at which this task is easiest to execute." .

prod:triggersHyperfocus
    a owl:ObjectProperty ;
    rdfs:domain prod:ADHSPattern ;
    rdfs:range  fc:Task ;
    rdfs:label "Triggers hyperfocus" ;
    rdfs:comment "Tasks that tend to trigger hyperfocus episodes for this user." .

prod:taskswitchCost
    a owl:DatatypeProperty ;
    rdfs:domain fc:Task ;
    rdfs:range  xsd:integer ;
    rdfs:label "Task-switch cost (minutes)" ;
    rdfs:comment "Estimated minutes of lost productivity when switching to this task mid-flow." .

# ── Named Individuals ──────────────────────────────────────────────────────

prod:Hyperfocus
    a prod:ADHSPattern ;
    rdfs:label "Hyperfocus" ;
    rdfs:comment "Intense, involuntary concentration on a stimulating task. Productive but hard to interrupt." .

prod:TimeBlindness
    a prod:ADHSPattern ;
    rdfs:label "Time Blindness" ;
    rdfs:comment "Difficulty perceiving the passage of time or estimating task duration accurately." .

prod:ActivationParalysis
    a prod:ADHSPattern ;
    rdfs:label "Activation Paralysis" ;
    rdfs:comment "Inability to begin a task despite knowing what to do. Common with high-stakes or boring tasks." .
```

---

## How the Agent Queries the Graph

Before generating a response, ZeroClaw queries the SurrealDB knowledge graph to inject relevant context into the LLM prompt.

**Query sequence:**

```
1. Parse incoming message → extract intent (e.g., "I can't start my tax return")

2. Query graph for active goals in finance domain
   SELECT * FROM goal WHERE user = $user_id AND domain = "finance" AND status = "active"

3. Query for related blocked tasks
   SELECT * FROM task WHERE goal IN $goals AND status = "blocked"

4. Query for relevant ADHS patterns
   SELECT * FROM concept WHERE type = "ADHSPattern" AND relatedTo = $task_id

5. Assemble context block:
   {
     active_goals: [...],
     blocked_tasks: [...],
     patterns: ["ActivationParalysis", "TimeBlindness"],
     recent_events: [...]
   }

6. Inject context into system prompt before LLM call

7. LLM response is grounded in the user's actual graph state
```

**Result:** The agent says "I see you've had 'complete tax return' blocked for 3 weeks — you've mentioned activation paralysis before. Want to try the 5-minute start technique?" rather than a generic response.

See [Multi-Agent Personalities](04-multi-agent-personalities.md) for how different personalities use this graph context differently.
