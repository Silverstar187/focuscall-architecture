# focuscall.ai — ZeroClaw Docker Image
# Multi-stage build: Rust builder → minimal Debian runtime
#
# Build on ARM64 host (Hetzner CAX21) or use buildx for cross-compile:
#   docker build -t zeroclaw:latest .
#   docker buildx build --platform linux/arm64 -t zeroclaw:latest .
#
# Source: https://github.com/zeroclaw-labs/zeroclaw

# ══════════════════════════════════════════════════════════════════
# Stage 1: Builder
# Build ZeroClaw from source on Debian (dynamic linking — simpler
# than musl static linking, compatible with runtime Debian image).
# ══════════════════════════════════════════════════════════════════
FROM rust:1.88-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    pkg-config \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Clone ZeroClaw source
RUN git clone --depth 1 https://github.com/zeroclaw-labs/zeroclaw.git /build

WORKDIR /build

# Build release binary (dynamically linked, works on Debian runtime)
# For ARM64 cross-compile from x86_64:
#   RUN rustup target add aarch64-unknown-linux-gnu && \
#       cargo build --release --target aarch64-unknown-linux-gnu
RUN cargo build --release

# ══════════════════════════════════════════════════════════════════
# Stage 2: Runtime
# Minimal Debian image — only runtime libs and the binary
# ══════════════════════════════════════════════════════════════════
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
# ca-certificates: needed for HTTPS calls to LLM APIs and Telegram
# curl: needed for HEALTHCHECK command
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r zeroclaw && useradd -r -g zeroclaw -d /home/zeroclaw -m zeroclaw

# Copy binary from builder stage
COPY --from=builder /build/target/release/zeroclaw /usr/local/bin/zeroclaw
RUN chmod +x /usr/local/bin/zeroclaw

# Workspace volume — mounted per-container by provision.py
# Contains: config.toml (no secrets), db/, logs/
VOLUME /workspace

# ZeroClaw reads config from this directory
ENV ZEROCLAW_CONFIG_DIR=/workspace

# LLM and bot keys are injected at runtime via Docker ENV (never baked into image):
#   ZEROCLAW_API_KEY      — LLM provider API key
#   TELEGRAM_BOT_TOKEN    — Telegram bot token

# Port is configured via workspace/config.toml (gateway.port)
# No EXPOSE needed — provision.py manages port allocation and routing

# Run as non-root
USER zeroclaw

# Health check — uses PORT env var if set, falls back to 42000
# ZeroClaw serves GET /health on its gateway port
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-42000}/health" | grep -q '"status"' || exit 1

ENTRYPOINT ["zeroclaw", "daemon"]
