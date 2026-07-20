# CLAUDE.md

Operating manual for a **KGA Life integration API**. This is the entry document for anyone —
human or agent — working in this repository. Read it before making changes, and follow it.

> **This file is managed.** It (and the `.claude/` tree beside it) is the shared KGA base
> config, synced from **[`KGA-Life/kga-claude-config`](https://github.com/KGA-Life/kga-claude-config)**
> by the devcontainer Feature / `make sync-claude-config`. **Do not edit the managed sections
> here — edit them in `kga-claude-config` so every repo gets the change.** Anything specific to
> *this* service goes in **`CLAUDE.local.md`** (never overwritten by a sync) and under
> **`reference/`** (the provider's own docs). Read both alongside this file.

---

## What this project is

This repository is a **first-party FastAPI service that wraps one third-party API** for KGA
Life, exposing a governed, least-privilege front door to it. A caller asks *our* service; our
service talks to the provider on their behalf using a single, centrally-managed connection.

The wider intent: every KGA integration is built this way — one small, uniform repo per
provider — so that access is consistent, auditable, and eventually **migratable into a single
central KGA API** that owns access/audit/logging for all integrations. Uniformity across the
fleet is what makes that migration clean; that is why the house style below is required, not
suggested.

**Which provider this repo wraps, and its specifics** (endpoints, auth model, scopes, data
shapes, module map) live in **`CLAUDE.local.md`** and **`reference/`** — read them first for
the concrete picture, then use this file for the shared conventions.

---

## Standing guardrails

Non-negotiable. They exist so a future contributor — human or agent — cannot silently leak a
secret or bypass governance. Treat any change that weakens them as a defect.

### 1. No secrets committed, ever
- **Credentials live only in a gitignored `.env`.** The committed **`.env.example`** holds
  **key names only** — never real values.
- **Any on-disk token/credential store is gitignored** (`.tokens/`, `*token*.json`, etc.). A
  rotating refresh token written there must never be committed.
- **No status endpoint and no log line ever prints a secret or token value.** Log metadata
  (token present? expiry? tenant confirmed?), never the token itself.
- Before committing, confirm `git status` shows no `.env` / token file tracked and that no
  secret-shaped value appears in the diff.

### 2. Governance seam stays clean
- Every data endpoint is gated by a **single auth dependency** (see *Architecture*). That one
  dependency is the deliberate attachment point for **caller authentication** and an **audit
  hook** — added with a one-line `Depends(...)` per router, without a rewrite.
- **Do not scatter auth or audit logic across routers.** Keep it at the seam so the future
  central KGA API can attach governance uniformly.

### Read vs write
This service may expose **read and/or write** endpoints — write access is expected for many
providers (ticketing, payments, etc.), so read-only is **not** a house rule. But **writes
raise the bar**: a write path must request the **narrowest** provider scope that works, must
pass through the audit seam, and should be called out in `CLAUDE.local.md`. Never request a
write scope a route doesn't use.

---

## House style (required)

Every generated KGA integration API follows these. They are the consistency backbone of the
fleet; deviate only with a reason stated in `CLAUDE.local.md`.

- **Layered structure, one direction only:** `routers → service → auth/token_store`, with
  `config` underneath everything. Routers are **thin** (bind path + params + `response_model`,
  call one service method, return); **all provider interaction lives in the service layer**
  (the provider client, auth headers, pagination, error mapping). Nothing lower reaches back up.
- **`X-API-Key` authentication on our own surface.** Our endpoints are guarded by an API-key
  dependency; `/health` is the one unauthenticated route.
- **`/health`** returns `200` when the app is up (unauthenticated, no provider call).
- **Audit middleware** logs every request (method, path, caller, outcome) — metadata only,
  never secrets. This is the governance signal the central KGA API will consume.
- **Typed Pydantic v2 models** as `response_model` on every route; `extra="allow"` for
  forward-compatibility with provider schema additions.
- **Team-neutral:** no personal git identity, no host-specific absolute paths, no dependence on
  one person's shell. Config selects environments; code never branches on `if env == "prod"`.

---

## Architecture / module map (baseline)

The concrete map for this service is in `CLAUDE.local.md`; the **baseline shape** every repo
starts from is:

```
app/
├── main.py            # app factory: load settings, wire service, register routers,
│                      #   OpenAPI/Swagger metadata, exception handler, /health, audit middleware
├── config.py          # pydantic-settings: dev/prod selection + all provider constants
│                      #   (endpoints, tenant/account id, the least-privilege scopes, base URL)
├── <provider>/
│   ├── token_store.py # TokenStore protocol + a file/secret-manager backend (sole writer of
│   │                  #   any rotating refresh token; the store path is injected, not imported)
│   ├── auth.py        # the provider's auth flow (OAuth2 / API key / HMAC); token refresh hook
│   └── service.py     # provider-SDK/HTTP wrapper: tenant header, pagination, error mapping
├── routers/
│   ├── deps.py        # the single auth dependency (the governance SEAM) + error handlers
│   └── <domain>.py    # one APIRouter per domain; mounted centrally in main.py
└── models/            # typed Pydantic v2 response models, grouped by domain
```

**The seam.** `app/routers/deps.py` holds the one dependency that gates every data route. Keep
caller-auth and the audit hook there — never inline in routers.

---

## Environments

Two environments, **`dev`** and **`prod`**, selected by the `APP_ENV` setting. They differ
**only in values** — base URL / callback host, log level, token-store path. **No code branches
on the environment**: one `Settings` model, environment-selected.

---

## Run / verify commands

Dependencies are managed with **`uv`** (`pyproject.toml` + `uv.lock` are the source of truth);
the venv targets **Python 3.14**, and the uv tool version is pinned via `[tool.uv]
required-version` so local and CI never drift. Use `uv run ...` for everything.

| Task | Command |
|---|---|
| Install / sync deps | `uv sync` |
| Run (dev) | `uv run uvicorn app.main:app --reload` |
| Open Swagger | `http://localhost:8000/docs` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format` |
| Tests | `uv run pytest` |
| Sync shared config | `make sync-claude-config` |

Health check: `GET /health` → `200`. CI runs `uv sync --locked` → `ruff check` →
`ruff format --check` → `pytest`; a green CI run on the PR head is a hard merge precondition.

---

## Conventions

Style and structure conventions are authoritative in **`.claude/rules/`** — follow them for all
code in this repo:

- **`.claude/rules/python-pep8.md`** — Python / PEP 8 style (ruff is the enforcer).
- **`.claude/rules/fastapi-conventions.md`** — routes, docstrings/Swagger, data models,
  folder/module structure, the layering and seam rules.

`ruff` (configured in `pyproject.toml`) enforces the lint/format baseline. A `PostToolUse` hook
in `.claude/settings.json` runs `ruff format` + `ruff check` after edits **for human developers
in a devcontainer** — note that this hook does **not** run inside a managed-agent session, so
**CI is the authoritative enforcement** for agent-authored code (the hook is convenience/parity,
not a guarantee).

---

## Contribution / PR workflow (for agents and humans)

- **Branch off a fresh `main`**; implement one issue per branch; keep commits focused.
- **Commit identity is the agent identity ("Claudette"), never a human's `gh`-authenticated
  account.** Open PRs and post comments via the **GitHub REST API + a scoped token**, not `gh`.
- **Request a review by posting an `@claude` comment on the PR** (not in the PR body) — the auto
  review is inline-only and silent on a clean diff, so the comment is what guarantees a visible
  review. Re-request on every subsequent push.
- **Merge is gated on three signals** — review greenlit ∧ acceptance criteria met ∧ CI green on
  the head SHA — and executed by a separate actor, not the coding agent. Do not self-merge.

---

## Per-service specifics

Read **`CLAUDE.local.md`** (this service's manual: provider, auth model, scopes, module map,
quirks) and **`reference/`** (the provider's own API docs, committed for offline reference).
This `CLAUDE.md` is the shared base; those two are where this repo says what makes it different.
