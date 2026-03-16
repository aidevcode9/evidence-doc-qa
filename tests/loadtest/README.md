# Load Testing (NFR-011, NFR-012)

Locust-based load tests for Evidence-Bound API. These are **not** run in CI.

## Prerequisites

```bash
pip install locust
```

## Running

```bash
# Start the API server
cd apps/api && uvicorn app.main:app --reload

# In another terminal, run Locust
locust -f tests/loadtest/locustfile.py --host http://localhost:8000

# Or headless mode with specific concurrency targets
locust -f tests/loadtest/locustfile.py \
  --host http://localhost:8000 \
  --headless \
  --users 50 \
  --spawn-rate 5 \
  --run-time 60s
```

## Targets

| Metric | Target | NFR |
|--------|--------|-----|
| p95 latency | < 8000ms | NFR-011 |
| Concurrent users | 50 | NFR-012 |

Open http://localhost:8089 for the Locust web UI with real-time charts.
