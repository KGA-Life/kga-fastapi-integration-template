# Auth0 dashboard setup — operator handoff

This service is a **validate-only** OAuth2 resource server: it verifies Auth0-issued bearer JWTs
and checks scopes, but provisions **nothing** in Auth0. The steps below are done **once per
environment** in the Auth0 dashboard by an operator. The code never performs them.

> The permission strings you create here MUST mirror the app's scope registry
> (`app/auth/scopes.py`). If they drift, routes will 403 legitimate callers.

## 1. Register the API (resource server)

**Applications → APIs → Create API.**

- **Name:** e.g. `KGA Integration Gateway`.
- **Identifier (audience):** a stable URI, e.g. `https://api.kga.co.za/gateway` (it does **not**
  need to resolve). **This value goes into the app env as `AUTH0_API_AUDIENCE`.**
- **Signing Algorithm:** **RS256** (the app validates RS256 only).

After creation, note your **tenant domain** (e.g. `kga.us.auth0.com`) → app env `AUTH0_DOMAIN`.
The app derives the issuer as `https://<AUTH0_DOMAIN>/` and fetches JWKS from
`https://<AUTH0_DOMAIN>/.well-known/jwks.json`.

## 2. Enable RBAC on the API

**APIs → (your API) → Settings → RBAC Settings:**

- Toggle **Enable RBAC** = on.
- Toggle **Add Permissions in the Access Token** = on.

This makes Auth0 put granted permissions in the JWT `permissions` claim, which the app reads
first (falling back to the space-delimited `scope` claim).

## 3. Define the permissions (scopes)

**APIs → (your API) → Permissions.** Add these — they must match the registry exactly.

**Finance domain — built and enforced now (create all 8):**

| Permission | Description |
|---|---|
| `finance:xero:read` | Read Xero data via the gateway |
| `finance:xero:write` | Write Xero data via the gateway |
| `finance:netcash:read` | Read Netcash data via the gateway |
| `finance:netcash:write` | Write Netcash data via the gateway |
| `finance:investec:read` | Read Investec data via the gateway |
| `finance:investec:write` | Write Investec data via the gateway |
| `finance:read` | Domain-wide finance read (superset of all `finance:*:read`) |
| `finance:write` | Domain-wide finance write (superset of all finance writes) |

**Reserved domains — create only when those domains are built out** (in the registry, no routes yet):
`csc:read` · `csc:write` · `legal:read` · `legal:write` · `audit:read` · `audit:write` ·
`hr:read` · `hr:write`.

> **Superset semantics** are enforced in the app, not in Auth0: granting `finance:write` implies
> `finance:xero:read`, and `finance:xero:write` implies `finance:xero:read`. So you can grant a
> caller the broad `finance:read`/`finance:write` instead of every leaf — but prefer the
> **narrowest** permission a caller actually needs (house rule; writes especially).

## 4. Grant permissions to callers

**Machine-to-machine callers** (other KGA services — the common case):

1. **Applications → Applications → Create Application → Machine to Machine.**
2. Authorize it for **this API**, and tick the specific permissions it needs (narrowest set).
3. Its **Client ID / Client Secret** run the **client-credentials** grant to obtain an access
   token with `audience=<AUTH0_API_AUDIENCE>`.

**End-user callers** (if any): define **Roles** (User Management → Roles) bundling the
permissions, assign roles to users; RBAC puts the union in the `permissions` claim.

## 5. Wire the app env

Set in the gitignored `.env` (see `.env.example` — names only there):

```
AUTH_PROVIDER=auth0
AUTH0_DOMAIN=<your-tenant-domain>         # e.g. kga.us.auth0.com  (no scheme, no trailing slash)
AUTH0_API_AUDIENCE=<the API Identifier from step 1>
AUTH0_ALGORITHMS=RS256
API_KEYS=<comma-separated caller X-API-Key values>   # the second (caller-auth) layer
```

## 6. Verify end-to-end

1. Get a token (M2M): `POST https://<AUTH0_DOMAIN>/oauth/token` with
   `grant_type=client_credentials`, `client_id`, `client_secret`, `audience=<AUTH0_API_AUDIENCE>`.
2. Call a gateway route with **both** layers:
   `GET /finance/xero/invoices` with header `Authorization: Bearer <token>` **and** `X-API-Key: <key>`.
   - right scope + valid key → `200`
   - missing/insufficient scope → `403` (`WWW-Authenticate: Bearer error="insufficient_scope"`)
   - missing/invalid token → `401` (`error="invalid_token"`); missing/invalid key → `401`.

## Tenant limits to be aware of

- Auth0 caps **permissions per API** and the number of scopes on a **client-credentials grant**
  (limits vary by plan). If you later mirror the full registry — including all reserved
  domains — check the tenant's current limits first and split callers across narrower grants
  rather than granting everything to one M2M app.
- The JWKS signing keys **rotate**; the app caches JWKS and refreshes on unknown `kid`, so no
  action is needed on rotation — but a very short-lived key rotation during an outage could cause
  transient 401s until the cache refreshes.
