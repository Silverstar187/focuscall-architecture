# Per-Tenant Architecture

> Related: [Vision](01-vision.md) | [Provisioning Flow](05-provisioning-flow.md) | [Tech Stack](06-tech-stack-and-capacity.md) | [README](README.md)

---

## Isolation Model

Every user gets a **completely isolated process and filesystem**. There is no shared ZeroClaw process, no shared database, no shared configuration.

| Resource | Isolation Level |
|----------|----------------|
| ZeroClaw process | 1 systemd service per user |
| SurrealDB | 1 embedded DB per user (separate directory) |
| Configuration | 1 config.toml per user |
| Port | 1 assigned port per user (42000 + N) |
| Filesystem | Separate directory tree per user |
| Logs | Separate log file per user |

---

## Directory Structure

```
/opt/focuscall/
├── users/
│   ├── {user_id_1}/
│   │   ├── config.toml          # ZeroClaw configuration (bot_token, llm_key, port, ...)
│   │   ├── db/                  # SurrealDB embedded data files
│   │   │   ├── data.db          # Main database file
│   │   │   └── wal/             # Write-ahead log
│   │   ├── files/               # User-uploaded files, documents, exports
│   │   │   └── uploads/
│   │   └── logs/                # Process logs for this user's instance
│   │       └── zeroclaw.log
│   ├── {user_id_2}/
│   │   └── ...
│   └── {user_id_N}/
│       └── ...
├── ontologies/                  # Shared read-only Turtle ontology files
│   ├── health.ttl
│   ├── finance.ttl
│   ├── productivity.ttl
│   └── relationships.ttl
├── registry.json                # Port assignment registry (user_id → port mapping)
├── provision.sh                 # Provisioning script
└── deprovision.sh               # Cleanup script
```

The `ontologies/` directory is **read-only shared** — all users share the same base ontology definitions. Per-user knowledge graph data lives in their `db/` directory.

---

## systemd Template Service

A single systemd template unit file handles all user instances. The `@` in the filename makes it a template — `%i` is replaced with the instance name (the user_id).

**File: `/etc/systemd/system/focuscall@.service`**

```ini
[Unit]
Description=focuscall.ai ZeroClaw instance for user %i
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=focuscall
Group=focuscall
WorkingDirectory=/opt/focuscall/users/%i
ExecStart=/usr/local/bin/zeroclaw --config /opt/focuscall/users/%i/config.toml
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5s
TimeoutStopSec=10s

# Resource limits per instance
MemoryMax=64M
CPUQuota=25%
TasksMax=32

# Logging
StandardOutput=append:/opt/focuscall/users/%i/logs/zeroclaw.log
StandardError=append:/opt/focuscall/users/%i/logs/zeroclaw.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/focuscall/users/%i

[Install]
WantedBy=multi-user.target
```

### Key systemd commands

```bash
# Start a user instance
systemctl start focuscall@{user_id}

# Enable at boot
systemctl enable focuscall@{user_id}

# Stop an instance
systemctl stop focuscall@{user_id}

# Check status
systemctl status focuscall@{user_id}

# Restart (e.g., after config change)
systemctl restart focuscall@{user_id}

# View logs
journalctl -u focuscall@{user_id} -f

# List all running instances
systemctl list-units 'focuscall@*' --state=running
```

---

## Port Assignment Scheme

Each user instance needs a unique TCP port for ZeroClaw's internal HTTP gateway.

**Range:** 42000–43999 (2000 possible instances per server)

**Registry file: `/opt/focuscall/registry.json`**

```json
{
  "next_port": 42003,
  "instances": {
    "usr_abc123": {
      "port": 42000,
      "created_at": "2026-01-15T10:30:00Z",
      "status": "running",
      "systemd_unit": "focuscall@usr_abc123.service"
    },
    "usr_def456": {
      "port": 42001,
      "created_at": "2026-01-16T14:22:00Z",
      "status": "running",
      "systemd_unit": "focuscall@usr_def456.service"
    },
    "usr_ghi789": {
      "port": 42002,
      "created_at": "2026-01-17T09:15:00Z",
      "status": "stopped",
      "systemd_unit": "focuscall@usr_ghi789.service"
    }
  }
}
```

The nginx reverse proxy uses this registry to route incoming requests to the correct ZeroClaw instance by user_id.

**nginx upstream routing (conceptual):**

```nginx
# Map user_id to upstream port (populated from registry.json via script)
map $http_x_user_id $backend_port {
    usr_abc123  42000;
    usr_def456  42001;
    default     0;
}

server {
    location /api/chat/ {
        proxy_pass http://127.0.0.1:$backend_port;
    }
}
```

---

## SurrealDB Embedded Per Tenant

SurrealDB v3.0+ runs in **embedded mode** — no separate database server process. Each ZeroClaw instance opens its own SurrealDB file directly via the Rust library.

```
/opt/focuscall/users/{user_id}/db/
├── data.db          # SurrealDB RocksDB-backed storage
└── wal/             # Write-ahead log for crash recovery
```

**Advantages of embedded mode:**
- No additional process or port per user
- Atomic startup/shutdown with ZeroClaw process
- Filesystem-level backup is sufficient (just copy the `db/` directory)
- Zero network overhead for graph queries

---

## Process Lifecycle

```
PROVISIONING            RUNNING              MAINTENANCE
     │                     │                     │
     ▼                     ▼                     ▼
provision.sh          Telegram message       systemctl restart
  └─ mkdir             arrives               focuscall@{uid}
  └─ write config.toml   │
  └─ assign port       ZeroClaw processes
  └─ systemctl start     │ reads knowledge graph
  └─ health check        │ calls LLM
                         │ stores new context
                         └─ sends reply
```

**Health check endpoint:**

```bash
# ZeroClaw exposes a /health endpoint on its port
curl -s http://127.0.0.1:{port}/health
# Expected: {"status":"ok","uptime":3600,"db":"connected"}
```

See [Provisioning Flow](05-provisioning-flow.md) for the complete onboarding sequence.
