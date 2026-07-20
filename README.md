# kga-fastapi-integration-template

The **KGA Life integration-API template**: a provider-agnostic FastAPI service that every
generated KGA integration API is created from. Each concrete service is a first-party
wrapper over **one** third-party provider — a caller asks *our* service, and our service
talks to the provider on their behalf behind a single, centrally-managed connection.

This template ships a working `example` provider so the four verification commands are
green out of the box. To build a real service, generate a repo from this template and
rename `example` throughout to the concrete provider (`freshdesk`, `netcash`, ...).

## What you get

- A layered, house-style FastAPI app that boots offline (no credentials needed to start).
- `X-API-Key` caller authentication on the data surface, with `/health` unauthenticated.
- Audit middleware that logs request metadata (method, path, whether a key was presented,
  status, duration) — **never** secrets or key values.
- A clean **provider-auth seam** (`app/routers/deps.py`) where caller-auth and the audit
  hook attach, ready for the future central KGA API.
- A pinned uv + Python 3.14 toolchain, a production `Dockerfile`, CI, and Dependabot.

## Architecture (layered, one direction only)

`routers → service → auth/token_store`, with `config` underneath everything. Routers are
**thin** (bind path + params + `response_model`, call one service method, return); all
provider interaction lives in the service layer.

```
app/
├── main.py            # app factory: settings, logging, router wiring, /health,
│                      #   audit middleware, exception handler
├── config.py          # pydantic-settings: env selection, API_PREFIX, caller keys,
│                      #   provider connection settings
├── example/           # the provider package — RENAME per service
│   ├── token_store.py # TokenStore ABC + atomic FileTokenStore (JSON on disk)
│   ├── auth.py        # provider-auth seam: ensure_valid_token / refresh (stub) / login_url
│   └── service.py     # ExampleService: httpx client, read + write, error mapping
├── routers/
│   ├── deps.py        # THE seam: require_api_key (caller auth) + require_provider_auth
│   │                  #   + the ProviderAuthError handler
│   └── example.py     # one APIRouter: GET /items, GET /items/{id}, POST /items
└── models/            # typed Pydantic v2 models (Item, ItemCreate); extra="allow"
```

`API_PREFIX` (in `app/config.py`, default `/integrations/example`) is the per-integration
URL namespace — rename it per service. `/health` deliberately lives outside it.

## House style

- **`X-API-Key` on the data surface.** When `API_KEYS` is configured, every data route
  requires a valid key; a missing/wrong key gets `401`. An empty `API_KEYS` leaves the
  surface unguarded (dev convenience) and logs a warning. `/health` never needs a key.
- **Audit middleware.** Every request is logged as metadata only — the key value is never
  logged, only whether one was presented. This is the governance signal the central KGA
  API will consume.
- **Provider-auth seam.** `require_provider_auth` ensures a provider token and returns the
  service; a missing token raises `ProviderAuthError`, handled app-wide as a `503` (JSON)
  or a `307` redirect to the login path (browser). Read + write are both demonstrated.
- **Forward-compatible models.** Every model sets `extra="allow"`, so unknown provider
  fields pass through untouched.

## Prerequisites

- **Python 3.14** (the project targets `py314`).
- **[`uv`](https://docs.astral.sh/uv/)**, pinned to **`0.10.11`** via `[tool.uv]
  required-version` in `pyproject.toml`. uv enforces it locally and CI installs the same
  version, so the dev loop and CI never drift. To adopt a newer uv, bump the pin here, in
  the `Dockerfile` base-image tag, and in this README together in one commit.

## Setup & run

```sh
# Install / sync dependencies (creates .venv from uv.lock)
uv sync

# Create your local env file from the committed template
cp .env.example .env      # Windows: copy .env.example .env

# Run the dev server with hot reload
uv run uvicorn app.main:app --reload
```

Then open Swagger at **http://localhost:8000/docs**. Liveness: `GET /health`.

Fill in `.env`: set `API_KEYS` (comma-separated caller keys) and the provider credentials
(`EXAMPLE_CLIENT_ID` / `EXAMPLE_CLIENT_SECRET`). `.env` is gitignored; the committed
`.env.example` holds key names only. The token store (`.tokens/`, `*token*.json`) is
gitignored too.

## Verify (the same steps CI runs)

```sh
uv run ruff check          # lint
uv run ruff format --check # format check (uv run ruff format to fix)
uv run pytest              # test suite (fully offline)
```

CI (`.github/workflows/ci.yml`) runs `uv sync --locked` → `ruff check` →
`ruff format --check` → `pytest` on every push to `main` and every PR. **CI is the
authoritative enforcement for agent-authored code**: the `PostToolUse` hook in
`.claude/settings.json` runs `ruff format` + `ruff check` after edits, but it is a
human-developer / devcontainer convenience only — it does **not** run inside a managed-agent
session, so a green CI run on the PR head is the real gate (not the hook).

## Docker

```sh
docker build -t kga-fastapi-integration-template .

# Run — persist any auth token store on a mounted volume at /data
docker run --rm -p 8000:8000 \
  --env-file .env \
  -e TOKEN_STORE_PATH=/data/example_token.json \
  -v kga-example-tokens:/data \
  kga-fastapi-integration-template
```

`docker compose up --build` does the same with a named volume wired in.

## Config: managed vs unmanaged

Config is materialized two ways (belt-and-braces): the **M1 devcontainer Feature**
(`.devcontainer/devcontainer.json` → `ghcr.io/kga-life/kga-claude-config/claude-config`)
materializes the shared config on build, and the template also **commits** a copy so agent
clones carry the steering config without a build step.

| Path | Status | Who owns it |
|---|---|---|
| `CLAUDE.md`, `.claude/` | **MANAGED** | Shared KGA base config — synced from `kga-claude-config`. Do not edit here; edit upstream so every repo gets the change. |
| `CLAUDE.local.md` | **UNMANAGED** | This service's manual (provider, auth model, scopes, quirks). Never overwritten by a sync. |
| `reference/` | **UNMANAGED** | The provider's own API docs, committed for offline reference. |

## Using this template

Generate a new repo from this template, then: rename the `app/example/` package and the
`example` router/models to the provider; set `API_PREFIX`, `EXAMPLE_API_BASE`, and the
credential fields in `app/config.py` + `.env.example`; wire `app/<provider>/auth.py` and
`service.py` to the real API; fill in `CLAUDE.local.md` and drop the provider docs into
`reference/`. Conventions are authoritative in `CLAUDE.md` and `.claude/rules/`.
