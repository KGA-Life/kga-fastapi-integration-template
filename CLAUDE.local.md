# CLAUDE.local.md

Per-service manual for **this** repo. **This file is UNMANAGED** — it is *never* overwritten by
a config sync (unlike `CLAUDE.md` and `.claude/`, the shared KGA base config). The fleet-wide
auth conventions are in `.claude/rules/auth-conventions.md`; this file records what is concrete
**here**.

> **What this repo is now.** The template has been reshaped from a single-provider wrapper into
> the **multi-domain gateway shell** — the shape the "future central KGA API" takes. It ships a
> provider-agnostic **auth module** (`app/auth/`) and a worked **finance domain** gateway
> (`app/domains/finance/`). The original single-provider `example` package is kept as the
> minimal reference for the "copy-a-folder to scaffold a new provider" story.

---

## Identity provider

- **IdP:** **Auth0 (Okta)**. Selected via `AUTH_PROVIDER=auth0`; the concrete implementation is
  `app/auth/auth0.py` (`Auth0Provider`). This service is a **validate-only resource server** — it
  verifies bearer JWTs and issues nothing.
- **Swap point:** `app/auth/provider.py` (`AuthProvider` ABC + `get_provider()`). A different IdP
  is a new module + an `AUTH_PROVIDER` value — no route or scope-registry change.
- **JWT validation:** JWKS (`https://<AUTH0_DOMAIN>/.well-known/jwks.json`), RS256 only, checks
  `iss` (`https://<AUTH0_DOMAIN>/`), `aud` (`AUTH0_API_AUDIENCE`), `exp`/`nbf`. Scopes come from the
  RBAC `permissions` claim when present, else the space-delimited `scope` claim. Library: `pyjwt[crypto]`.

## Two auth layers (both enforced on every data route)

- **Caller auth — `X-API-Key`** (`require_api_key`): which service is calling. Configured via `API_KEYS`.
- **Principal authorization — JWT scopes** (`require_scopes(...)`): what the Auth0 principal may do.
- Both are re-exported from the seam `app/routers/deps.py`; routes attach both. `/health` needs neither.

## Gateway topology & scopes

- **URL shape:** `/<domain>/<provider>/…`. Built out this round: **`finance`** with **`xero`**,
  **`netcash`**, **`investec`** provider sub-packages (`/finance/xero/…` etc.).
- **Reserved domains** (in the scope registry, not yet built): `csc`, `legal`, `audit`, `hr`.
- **Scope registry — single source of truth:** `app/auth/scopes.py`. Shape `<domain>:<provider>:<action>`
  with domain-wide `<domain>:<action>` supersets and semantics domain⇒provider, write⇒read.
- **Scopes enforced on the finance routes:**

  | Route | Method | Scope |
  |---|---|---|
  | `/finance/xero/invoices` | GET / POST | `finance:xero:read` / `finance:xero:write` |
  | `/finance/netcash/transactions` · `/finance/netcash/payments` | GET / POST | `finance:netcash:read` / `finance:netcash:write` |
  | `/finance/investec/accounts` · `/finance/investec/payments` | GET / POST | `finance:investec:read` / `finance:investec:write` |

  The provider `service.py` methods are **stubs** (`# TODO: wire to the real API`) — real Xero/Netcash/
  Investec integration is out of scope here (each has, or will have, its own upstream).

## Module map (specifics)

- `app/auth/provider.py` — `AuthProvider` ABC, `get_provider()` (the swap point), `InvalidTokenError`
  (→401), `InsufficientScopeError` (→403).
- `app/auth/auth0.py` — `Auth0Provider` (validate-only; lazy `PyJWKClient`; injectable
  `signing_key_resolver`/`settings` for offline tests).
- `app/auth/scopes.py` — scope registry + `satisfies(granted, required)`.
- `app/auth/dependencies.py` — `current_principal`, `require_scopes(...)` factory.
- `app/domains/finance/router.py` — mounts the three provider subrouters under `/finance`.
- `app/domains/finance/<provider>/{router,service,models}.py` — thin router + stub service + models.
- `app/routers/deps.py` — the seam: re-exports `require_api_key` + `require_scopes`/`current_principal`.

## Config / env (names only; values in gitignored `.env`)

`AUTH_PROVIDER` (default `auth0`), `AUTH0_DOMAIN`, `AUTH0_API_AUDIENCE`, `AUTH0_ALGORITHMS`
(default `RS256`), and `API_KEYS` (comma-separated caller keys). See `.env.example`. Auth config is
validated at **use-time** (`Settings.require_auth0_config()`), never at import — the app boots offline.

## Auth0 dashboard setup (operator handoff)

The code provisions nothing in Auth0. The exact dashboard steps (register the API/resource server
with the audience identifier, enable RBAC + "add permissions in the access token", create the
permission strings that mirror the registry, create the M2M grant) plus tenant-limit notes are in
**`reference/auth0-ui-handoff.md`**.

## Adding a new domain / provider

1. Add the scope constants to `app/auth/scopes.py` (the registry validates route scopes against it).
2. Copy an existing provider folder (e.g. `app/domains/finance/xero/`) to
   `app/domains/<domain>/<provider>/`; adjust routes, `require_scopes(...)`, models, stub service.
3. Add/extend the domain `router.py`; `include_router` it in `app/main.py`.
4. Create the matching permission in the Auth0 dashboard and add it to the M2M/user grants.
5. Add tests (route allow/deny + the scope), keep the suite offline and coverage ≥ 80%.

## Quirks

- This FastAPI/starlette build keeps `include_router`'d routers as internal wrappers — enumerate
  the live surface via `app.openapi()["paths"]`, not `app.routes` / `router.routes`.
- The audit middleware logs the **presence** of an `X-API-Key` only, never the value; the same
  no-secrets rule applies to bearer tokens and claims.

## Reference docs

Provider/API docs and the Auth0 UI handoff live under **`reference/`** (also unmanaged).
