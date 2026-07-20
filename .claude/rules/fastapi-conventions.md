# FastAPI conventions

Authoritative FastAPI conventions for KGA Life integration APIs, referenced by `CLAUDE.md`.
Each service is a **first-party wrapper over one third-party API**. Every convention below
serves two house rules: **thin routers, all provider logic in the service**, and a **single
governance seam** for auth/audit. Read alongside `.claude/rules/python-pep8.md`. The concrete
provider, URL prefix, and scopes for this repo are in `CLAUDE.local.md`.

## 1. Routes

- **One `APIRouter` per domain**, matching the files in `app/routers/`. Mounting is central:
  `app/main.py` includes each router — do **not** set the prefix on individual routers.
- **Every route lives under this service's namespaced prefix** — `/<domain>/<provider>/`
  (e.g. `/finance/xero/`, `/support/freshdesk/`), declared once in `main.py`. The concrete
  prefix for this repo is in `CLAUDE.local.md`.
- **Method matches intent:** `GET` for reads; `POST`/`PUT`/`PATCH`/`DELETE` only where the
  service genuinely writes to the provider. A write route must use the narrowest provider
  scope that works and pass through the auth seam like every other route.
- **Type every path and query parameter.** Use `X | None = None` for optional query params;
  let FastAPI do validation and coercion. Type request bodies with Pydantic models.
- **`tags=[...]` per domain** so Swagger groups endpoints (e.g. `tags=["contacts"]`).
- **Every data route declares the auth dependency** via `Depends`. It lives in
  `app/routers/deps.py` (the single seam dependency) and gates access. Attach it per route or
  on the router's `dependencies=[...]`.
- **Routers are THIN.** No provider SDK/HTTP calls, no auth header, no pagination, no error
  mapping in a router. A route binds path + params + `response_model`, calls one service
  method, and returns. All provider interaction goes through `app/<provider>/service.py`.

```python
"""Contacts routes: read-only views over the provider's contacts."""

from fastapi import APIRouter, Depends

from app.models.contact import Contact
from app.routers.deps import require_auth
from app.provider.service import ProviderService, get_service

router = APIRouter(tags=["contacts"], dependencies=[Depends(require_auth)])


@router.get("/contacts/{contact_id}", response_model=Contact)
def get_contact(contact_id: str, service: ProviderService = Depends(get_service)) -> Contact:
    """Return a single contact by its id."""
    # WHY: pagination, auth header, and error mapping all live in the service —
    # the router stays a thin binding of path + response_model + auth.
    return service.get_contact(contact_id)
```

## 2. Comments and docstrings

- **Each route function has a docstring; its first line becomes the Swagger summary.** Keep it
  a short imperative sentence describing what the caller gets back.
- For richer docs use the decorator fields: `summary=`, `description=` (supports Markdown), and
  `response_description=`. Prefer the docstring for the summary.
- **Comment WHY, not WHAT.** The signature and `response_model` already say what a route
  returns; comments explain non-obvious decisions (why a param is required, why a provider
  quirk is handled a certain way).

## 3. Swagger / OpenAPI

- **`/docs` is the single source of truth for the endpoint surface.** Keep it accurate; do not
  maintain a separate hand-written endpoint list.
- **Set `response_model` on every route** — it drives the schema, response filtering, and the
  example shown in Swagger.
- **Give the app title, description, and version** in the `FastAPI(...)` constructor in
  `app/main.py` (version tracks `pyproject.toml`).
- **Group with domain `tags`** so the Swagger UI sections match the routers.
- **Provide example values** where they aid a caller — via `Field(examples=[...])` on model
  fields or `examples=` on `Query`/`Path` params.

```python
app = FastAPI(
    title="KGA <Provider> API",
    description="First-party wrapper over the <Provider> API.",
    version="0.1.0",
)
```

## 4. Data models

- **Typed Pydantic v2 response models** that mirror the provider fields a route returns. Do not
  attempt to model every provider schema — type the primary fields and let the rest pass through.
- **Every model sets** `model_config = ConfigDict(extra="allow", populate_by_name=True)`.
  `extra="allow"` is deliberate forward-compatibility: unknown provider fields pass through
  untouched instead of being dropped, so a provider schema addition does not silently lose data.
  `populate_by_name=True` lets the model be built from either the alias or the field name.
- **Type primary fields with their wire names via `Field(alias=...)`** (providers often speak
  PascalCase or camelCase JSON), while the Python attribute stays `snake_case` (PEP 8).
- **Models live in `app/models/`**, grouped by domain, and are the `response_model` for routes
  (and the request body type for writes). Routers import from `app.models`; they never define
  response shapes inline.

```python
"""Contact response model mirroring the provider's contact schema."""

from pydantic import BaseModel, ConfigDict, Field


class Contact(BaseModel):
    # extra="allow" -> unmodelled provider fields pass through (forward-compatible);
    # populate_by_name=True -> build from either alias or snake_case name.
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    contact_id: str = Field(alias="ContactID")
    name: str = Field(alias="Name")
    email_address: str | None = Field(default=None, alias="EmailAddress")
```

## 5. Folder / module structure

```
app/
├── main.py            # app factory: settings, router registration, OpenAPI metadata,
│                      #   exception handler, /health, audit middleware
├── config.py          # pydantic-settings: env selection + provider constants + scopes
├── <provider>/
│   ├── token_store.py # TokenStore protocol + backend; sole writer of any refresh token
│   ├── auth.py        # the provider's auth flow (OAuth2 / API key / HMAC); refresh hook
│   └── service.py     # provider wrapper: auth header, pagination, error mapping
├── routers/
│   ├── deps.py        # the single auth dependency (the SEAM) + error handlers
│   └── <domain>.py    # one router per domain (contacts, transactions, ...)
└── models/            # typed Pydantic response/request models, grouped by domain
```

**Layering rule (one direction only):** `routers → service → auth/token_store`, with `config`
underneath everything. Routers depend on the service; the service depends on
`auth`/`token_store`; nothing lower reaches back up. A router must never import the provider
SDK or reach past the service into `auth`/`token_store` directly.

**The seam principle.** `app/routers/deps.py` holds the single auth dependency that gates every
data route. That one dependency is the deliberate attachment point for **caller authentication**
and an **audit hook** — added with a one-line `Depends(...)`, without rewriting routers. Keep
auth logic there; never scatter it across routers. This is the seam the central KGA API will
attach governance to.
