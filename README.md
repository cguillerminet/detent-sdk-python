# detent-sdk

Typed Python client for the [Detent](https://detent.fr) rate-limiting API. Sync and async, one dependency (httpx).

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

### FastAPI

Enforce limits with a dependency — it runs before the handler, composes per-route,
and shows up in the OpenAPI schema. Create one client in the lifespan and reuse it:

```python
from contextlib import asynccontextmanager
from math import ceil

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from detent import AsyncDetent, DetentLeaseDenied


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncDetent(api_key="dt_live_...") as rg:
        app.state.detent = rg
        yield


app = FastAPI(lifespan=lifespan)


def rate_limit(namespace: str):
    async def dep(request: Request, response: Response) -> None:
        rg: AsyncDetent = request.app.state.detent
        # Throttle identity: an API key, a user id, or the client IP. Trust
        # X-Forwarded-For only if it's set by a proxy you control.
        key = request.client.host if request.client else "anon"
        r = await rg.limit(namespace=namespace, key=key)
        response.headers["X-RateLimit-Remaining"] = str(r.remaining)
        if not r.allowed:  # a verdict, not an exception — you emit the 429
            retry_after = max(1, ceil(r.reset_ms / 1000))
            raise HTTPException(429, "Rate limit exceeded",
                                headers={"Retry-After": str(retry_after)})
    return dep


@app.get("/search", dependencies=[Depends(rate_limit("api"))])
async def search(q: str):
    return {"q": q}
```

For a **concurrency cap**, hold a lease for the handler's lifetime with a `yield`
dependency — the slot is auto-released even if the handler raises, and a full
namespace raises `DetentLeaseDenied`:

```python
async def with_slot(request: Request):
    rg: AsyncDetent = request.app.state.detent
    key = request.client.host if request.client else "anon"
    try:
        async with rg.lease(namespace="jobs", key=key):
            yield
    except DetentLeaseDenied:
        raise HTTPException(429, "Too many concurrent requests")


@app.post("/report", dependencies=[Depends(with_slot)])
async def generate_report():
    ...
```

The account-level policy errors (`DetentQuotaExceeded` 429, `DetentPaymentRequired`
402) propagate out of `limit()`/`lease()`; register an `@app.exception_handler` for
each to turn them into a response.

### Configuration

| Option      | Default                    | Notes                                                    |
|-------------|----------------------------|----------------------------------------------------------|
| `api_key`   | — (required)               | `dt_live_…` / `dt_test_…`                                 |
| `base_url`  | `https://api.detent.fr`   | Override for self-host / tests                            |
| `timeout`   | `1.0`                      | Seconds; client-side transport timeout                    |
| `fail_mode` | `"open"`                   | `"open"` allows, `"closed"` denies on a degraded backend  |
| `on_error`  | `None`                     | Called on a degraded (transport/5xx) `limit()` call       |

`limit()` never raises on a degraded backend (transport error or 5xx) — it
returns a result with `degraded=True`. A `4xx` (bad key, plan gate, unknown
rule) raises `DetentAPIError`.

**`acquire()` / `lease()` do *not* fail open** — unlike `limit()`, they raise
`DetentTransportError` when Detent is unreachable, regardless of `fail_mode`. A
failed-open acquire would return no `lease_id`, so the work would run holding a
slot it can never release (a lease leak). Raising lets you decide whether to
proceed or shed load. This is distinct from the server's own Redis fail-open,
where the API still returns `200` with `allowed=True` and a `None` `lease_id`.

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
