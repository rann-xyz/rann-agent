# RANN Agent — Performance

> **SLO enforcement:** CI blocks merges when any benchmark regresses >20% vs baseline.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         RANN Agent                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   HTTP      │    │    LLM      │    │   DB Connection     │  │
│  │   Pool      │    │   Client    │    │   Pool (SQLite)     │  │
│  │ 100 conn    │    │  reuse      │    │  WAL + mmap + 5 conn│  │
│  │ keepalive   │    │             │    │                     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                      │              │
│         ▼                  ▼                      ▼              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Cache Manager                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │    │
│  │  │ LLM resp    │  │ Tool result │  │ Embeddings      │  │    │
│  │  │ TTL: 1h     │  │ TTL: 5min   │  │ TTL: 24h        │  │    │
│  │  │ (in-mem or  │  │ (in-mem or  │  │ (vector store)  │  │    │
│  │  │  Redis)     │  │  Redis)     │  │                 │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Context Window Manager                     │    │
│  │  Strategy: keep system + recent, drop middle            │    │
│  │  200k token window (claude-sonnet-4 / claude-opus-4)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               State Machine (12 states)                 │    │
│  │  QUEUED → ANALYZING → CONTEXT_READY → PLANNING → …      │    │
│  │  Persisted to ~/.rann_agent/state/ for resume            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Caching

RANN uses a three-tier cache strategy:

| Tier | What | TTL | Backend |
|------|------|-----|---------|
| **LLM response** | Full prompt → completion mapping | 1 hour | Memory dict or Redis |
| **Tool result** | Tool name + parameters → output | 5 minutes | Memory dict or Redis |
| **Embedding** | Text → vector (future) | 24 hours | Vector store |

**Cache key format:** `sha256(json.dumps(messages, sort_keys=True))[:16]` — deterministic, collision-resistant.

**When to invalidate:**
- Tool result cache: cleared on tool schema change
- LLM response cache: cleared on model change or system prompt change
- Embedding cache: cleared on embedding model change

---

## Connection Pooling

### HTTP Pool (`rann_agent/utils/http_pool.py`)
- **Max connections:** 100
- **Keepalive:** enabled, reused across requests
- **Timeout:** 30s per request
- **Backpressure:** semaphore limits concurrent in-flight requests

### Database Pool (`rann_agent/storage/pool.py`)
- **Pool size:** 5 SQLite connections
- **Pragmas:** `journal_mode=WAL`, `synchronous=NORMAL`, `cache_size=-64000` (64 MB), `temp_store=MEMORY`, `mmap_size=268435456` (256 MB)
- **Connection acquire:** < 50 ms p99
- **Health check:** `SELECT 1` on acquire; dead connections replaced

### LLM Client Reuse
- `llm_client_reuse_enabled: true` keeps the HTTP client alive across calls
- New connections are expensive (TCP + TLS handshake); reuse avoids that cost

---

## Context Trimming

The `ContextWindowManager` (`rann_agent/utils/context_window.py`) trims conversation history when it exceeds the model's context limit.

**Strategy:** `truncate` — keep system prompt (head) + recent messages (tail), drop middle.

```
Before trim (2000 msgs, ~180k tokens):
┌────────────────────────────────────────────────────┐
│ [system] [msg_1] [msg_2] ... [msg_1998] [msg_1999] │
└────────────────────────────────────────────────────┘

After trim (system + last 10 = 11 msgs, ~3k tokens):
┌──────────────────────────┐
│ [system] ... [msg_1990]  │
└──────────────────────────┘
```

- **head_count:** 1 (always keep system prompt)
- **tail_count:** 10 (always keep 10 most recent)
- **Token estimate:** ~4 chars/token (3 for code-heavy content)
- **Reserved:** 2000 tokens for system prompt + response overhead

---

## SLO Table

| Operation | SLO (p99) | Measured | Notes |
|-----------|-----------|----------|-------|
| Cache hit (memory) | < 100 µs | ~0.9 µs | dict lookup |
| Cache miss (memory) | < 500 µs | ~10 µs | dict write |
| Cache key generation | < 10 µs | ~55 µs | sha256 hexdigest |
| LLM key stability | < 5 µs | ~44 µs | 2× key gen |
| Context trim 100 msgs | < 10 ms | ~0.49 ms | well within SLO |
| Context trim 1000 msgs | < 50 ms | ~5.0 ms | well within SLO |
| State 100 transitions | < 5 ms | ~0.15 ms | dict + logic |
| DB connection acquire | < 50 ms | ~27 µs | pool get + SELECT 1 |

> **Note:** SLOs are measured at p99 (median for pytest-benchmark). Real-world p99 may be higher due to system noise. CI uses 20% regression threshold.

---

## Running Benchmarks

### Local

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run benchmarks (no GC interference)
pytest tests/benchmarks/test_benchmark.py -v --benchmark-disable-gc

# Save a new baseline
pytest tests/benchmarks/test_benchmark.py -v --benchmark-disable-gc --benchmark-save=baseline

# Compare against saved baseline
pytest tests/benchmarks/test_benchmark.py -v --benchmark-disable-gc --benchmark-compare

# Fail if regression > 20%
pytest tests/benchmarks/test_benchmark.py -v --benchmark-disable-gc \
  --benchmark-compare --benchmark-compare-fail-percent=20
```

### CI Regression Enforcement

The `benchmark` job in `.github/workflows/ci.yml`:

1. **First run** (no baseline): saves initial baseline to `benchmarks/baseline/benchmark_baseline.json`
2. **Subsequent runs:** compares current results vs baseline using `--benchmark-compare`
3. **Fail threshold:** `--benchmark-compare-fail-percent=20` — any benchmark >20% slower than baseline fails CI

```
# To update baseline after intentional change:
pytest tests/benchmarks/test_benchmark.py --benchmark-save
# Then commit the new benchmarks/baseline/benchmark_baseline.json
```

---

## Baseline File Format

`benchmarks/baseline/benchmark_baseline.json` is a `pytest-benchmark` JSON export containing:

- `machine_info`: CPU, Python version, OS (for cross-machine awareness)
- `commit_info`: git SHA of the baseline
- `benchmarks[]`: per-test stats (min, max, mean, median, stddev, rounds, OPS)

CI compares the **mean** time of each benchmark. The 20% threshold applies to `(current_mean - baseline_mean) / baseline_mean`.

---

## Files

```
rann-agent/
├── requirements-dev.txt          # Dev deps (pytest-benchmark, ruff, pip-audit)
├── .pre-commit-config.yaml       # ruff, black, pre-commit-hooks
├── .github/workflows/ci.yml      # Includes benchmark job
├── benchmarks/
│   └── baseline/
│       └── benchmark_baseline.json  # Saved baseline numbers
├── tests/
│   └── benchmarks/
│       └── test_benchmark.py     # pytest-benchmark tests
└── PERFORMANCE.md                # This file
```