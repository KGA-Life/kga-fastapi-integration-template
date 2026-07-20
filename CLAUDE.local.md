# CLAUDE.local.md

Per-service manual for **this** KGA integration API. **This file is UNMANAGED** — it is
*never* overwritten by a config sync (unlike `CLAUDE.md` and `.claude/`, which are the
shared KGA base config). Everything specific to the provider this repo wraps goes here.

Fill in the blanks below when you generate a concrete service from the template, then
delete this notice.

---

## Provider

- **Provider name:** _<e.g. Freshdesk, Netcash, Investec>_
- **What we expose:** _<one line: which provider domains/resources this service fronts>_
- **URL namespace (`API_PREFIX`):** _<e.g. `/support/freshdesk`>_ — set in `app/config.py`;
  rename the `app/example/` package and the `example` router to match.
- **Base URL:** _<the provider API base; set `EXAMPLE_API_BASE` / rename the setting>_

## Auth model

- **Provider auth scheme:** _<OAuth2 authorization-code / API key / HMAC / basic>_
- **Scopes / permissions requested:** _<list the NARROWEST scopes the routes actually use>_
- **Token rotation:** _<does the provider rotate refresh tokens? if so, persistence of the
  rotated token via the TokenStore is the key correctness property>_
- **Caller auth:** X-API-Key (house default). _<note any deviation and why>_

## Read vs write

- **Read routes:** _<list>_
- **Write routes:** _<list, with the provider scope each requires — writes raise the bar>_

## Module map (specifics)

- `app/<provider>/service.py` — _<endpoints called, pagination style, error quirks>_
- `app/<provider>/auth.py` — _<the real refresh/exchange flow>_
- `app/models/` — _<the domain models and their wire aliases>_

## Provider quirks

- _<rate limits, pagination oddities, envelope shapes, casing, anything non-obvious>_

## Reference docs

The provider's own API documentation is committed under **`reference/`** (also unmanaged).
