# detent-sdk

Typed Python client for the [Detent](https://detent.dev) rate-limiting API. Sync and async, one dependency (httpx).

```bash
pip install detent-sdk
```

## Usage

```python
from detent import Detent

rg = Detent(api_key="dt_live_...")

# Rate-limit check (fails open by default on transport error or 5xx)
r = rg.limit(namespace="api", key=user_id)
if not r.allowed:
    ...  # return HTTP 429

# Concurrent-limit lease (auto-released)
with rg.lease(namespace="jobs", key=user_id):
    run_expensive_job()

# Read-only usage stats
stats = rg.get_stats(namespace="api")
```

### Async

```python
from detent import AsyncDetent

async with AsyncDetent(api_key="dt_live_...") as rg:
    r = await rg.limit(namespace="api", key=user_id)
    async with rg.lease(namespace="jobs", key=user_id):
        await run_expensive_job()
```

### Configuration

| Option      | Default                    | Notes                                                    |
|-------------|----------------------------|----------------------------------------------------------|
| `api_key`   | — (required)               | `dt_live_…` / `dt_test_…`                                 |
| `base_url`  | `https://api.detent.dev`   | Override for self-host / tests                            |
| `timeout`   | `1.0`                      | Seconds; client-side transport timeout                    |
| `fail_mode` | `"open"`                   | `"open"` allows, `"closed"` denies on a degraded backend  |
| `on_error`  | `None`                     | Called on a degraded (transport/5xx) `limit()` call       |

`limit()` never raises on a degraded backend (transport error or 5xx) — it
returns a result with `degraded=True`. A `4xx` (bad key, plan gate, unknown
rule) raises `DetentAPIError`.

When an account exceeds its monthly hard ceiling the API returns `429`, and
`limit()`/`acquire()` raise **`DetentQuotaExceeded`** (a `DetentAPIError`
subclass carrying `status`/`body`). It is **never** failed open — the cap is a
deliberate block. Catch it to alert or prompt an upgrade:

```python
from detent import DetentQuotaExceeded

try:
    result = client.limit(namespace="api", key=user_id)
    if not result.allowed:
        ...  # routine per-key rate deny → return HTTP 429
except DetentQuotaExceeded:
    ...  # account over its monthly ceiling → page ops / upgrade nudge
```
