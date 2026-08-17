# Auth conventions

Authoritative authentication/authorization conventions for KGA Life integration APIs,
referenced by `CLAUDE.md`. Read alongside `.claude/rules/fastapi-conventions.md`. The concrete
identity provider, the scopes this repo actually enforces, and any deviations are in
`CLAUDE.local.md`.

Two ideas govern everything here: **two complementary auth layers** (who is calling vs. what the
caller may do), and a **provider-agnostic seam** so the identity provider can be swapped without
touching routes. The default provider is **Auth0 (Okta)**; nothing below is Auth0-specific except
the one concrete provider module.

## 1. Two layers, both at the seam

Every data route passes through **two** checks; `/health` through neither.

- **Caller authentication — `X-API-Key`.** Answers *which service is calling*. The house default,
  enforced by `require_api_key` in `app/routers/deps.py`. Unchanged by anything here.
- **Principal authorization — OAuth2 JWT scopes.** Answers *what this authenticated principal may
  do*. A bearer access token (issued by the IdP) is validated and its scopes checked per route.

Both attach at the single governance seam (`app/routers/deps.py`), never inline in a router, and
neither replaces the other — a data route carries `require_api_key` **and** a scope check. This is
the seam the future central KGA API attaches governance to.

## 2. Provider-agnostic seam (swap the IdP in one file)

- **All IdP interaction lives behind an `AuthProvider` ABC** in `app/auth/provider.py`
  (`verify(token) -> Principal`). The concrete implementation for the current IdP lives in a
  single module — `app/auth/auth0.py` — and is selected by config (`AUTH_PROVIDER`) through
  `get_provider()`. Swapping IdP (Auth0 → Cognito/Entra/…) is a **new provider module + a config
  flag** — no route, no scope-registry, and no dependency change.
- **Never import the IdP or JWT library outside the concrete provider module.** `provider.py`,
  `models.py`, `scopes.py`, and `dependencies.py` stay vendor-neutral. Enforce it: a grep for the
  JWT/IdP library in any module other than the concrete provider is a defect.

## 3. Validate-only resource server

- The service is an OAuth2 **resource server**: it **validates** bearer JWTs and **issues
  nothing**. No token minting, refresh, or storage in the auth module.
- Validation is complete: fetch the IdP **JWKS**, verify the **RS256** signature, and check
  `iss`, `aud` (this API's identifier/audience), and `exp`/`nbf`. Pin the algorithm to an explicit
  allowlist (`RS256`) — never accept `alg` from the token unchecked, never `alg=none`.
- Build the `Principal` from the validated claims: `sub`, and scopes from the RBAC `permissions`
  claim when present, else the space-delimited `scope` claim.

## 4. Scope taxonomy and the central registry

- **Hierarchical scopes: `<domain>:<provider>:<action>`** (e.g. `finance:xero:read`,
  `finance:netcash:write`), plus domain-wide `<domain>:<action>` (e.g. `finance:read`). Domains
  map to URL paths (`/finance/xero/…`); providers are the wrapped third parties; actions are
  `read`/`write`.
- **One registry is the single source of truth:** `app/auth/scopes.py` enumerates every known
  scope so the set is testable and diffable against the IdP dashboard. `require_scopes(...)`
  validates each scope string against the registry at wiring time — a typo fails loudly, not
  silently open.
- **Superset semantics (defined AND tested):** a domain-wide grant implies its provider scopes
  (`finance:read` ⇒ `finance:xero:read`); `write` implies `read` at the same specificity
  (`finance:xero:write` ⇒ `finance:xero:read`, `finance:write` ⇒ `finance:xero:read`). A narrow
  grant never satisfies a broader requirement, and scopes never cross domains or providers.
- **Writes take the narrowest scope that works** (house rule) — a write route requires
  `…:write`, never a broad grant it does not use.

## 5. Enforcement in routes

- A route declares its requirement with the seam dependency `require_scopes("<domain>:<provider>:<action>")`;
  it yields the `Principal` on success. Attach caller-auth (`require_api_key`) alongside it. Use
  module-level `Depends(...)` singletons (avoid ruff B008), exactly as the base router style does.
- Routers stay **thin**: bind path + params + `response_model` + the two auth dependencies, call
  one service method, return. No token parsing or scope logic in a router.

## 6. Error semantics

- **`401`** — missing/invalid caller token (bad or absent bearer, failed JWT validation).
  Respond per RFC 6750: `WWW-Authenticate: Bearer error="invalid_token"`.
- **`403`** — authenticated but insufficient scope: `WWW-Authenticate: Bearer error="insufficient_scope"`.
- Keep these **distinct from `503` `ProviderAuthError`**, which means *our* service lacks a usable
  **upstream-provider** token (a server-side gap, handled at its own seam) — not a caller mistake.
- Error bodies are safe and secret-free: never echo a token, key, or claim value in a response.

## 7. Offline & testability invariant

- **No network and no credentials at import or app startup.** The app boots and `/docs` renders
  with no `.env`. IdP config is validated at **use-time** (a `require_*_config()` fail-fast that
  names the missing env var), never at import.
- **JWKS fetch is lazy and injectable.** The concrete provider accepts an injectable
  signing-key resolver (and settings) so tests validate real RS256 tokens signed with a
  test-local key — **fully offline, no live IdP**. The whole suite runs offline; a session-scoped
  socket guard should make an accidental network call fail loudly.
- Route/scope tests override the `current_principal` seam to inject a `Principal` with controlled
  scopes — exercising authorization without minting real JWTs.

## 8. Secrets & audit

- IdP tenant/domain/audience come from the gitignored `.env`; `.env.example` carries **key names
  only**. No secrets committed, ever (the standing guardrail).
- The audit middleware logs **metadata only** — method, path, key/token *presence*, status,
  duration — **never** a token, key, or claim value.

## 9. IdP dashboard configuration is an ops handoff

- The code never provisions the IdP. Creating the API/resource server (with the audience
  identifier), enabling RBAC + "add permissions in the access token", defining the permission
  strings **to mirror the scope registry**, and creating machine-to-machine grants are **dashboard
  steps done by an operator**. Ship the exact list as a handoff checklist under `reference/`, and
  note any IdP tenant limits (permission counts, M2M grants) there.
