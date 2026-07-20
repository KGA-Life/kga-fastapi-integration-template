# Python / PEP 8 style guide

Authoritative Python style for KGA Life integration APIs, referenced by `CLAUDE.md`. It is
PEP 8 as applied across the KGA fleet, tuned to the settings in each repo's `pyproject.toml`.
The enforced tool is **ruff** — this document explains intent; ruff decides pass/fail.

## Enforcement (ruff is the source of truth)

- Format: `uv run ruff format`
- Lint: `uv run ruff check` (add `--fix` to auto-apply safe fixes)
- Run both before committing. Do not hand-tune style that ruff would rewrite — let the
  formatter own whitespace, quotes, and line wrapping so diffs stay about behaviour.

Config lives in `pyproject.toml` and is the single source of truth. Baseline settings:

- `line-length = 100`
- `target-version = "py314"` (Python 3.14)
- Enabled lint families: `E, F, I, W, N, UP, B`
  - `E` / `W` — pycodestyle errors and warnings (PEP 8 layout)
  - `F` — pyflakes (unused imports/vars, undefined names)
  - `I` — isort (import ordering; see below)
  - `N` — pep8-naming (the naming rules below)
  - `UP` — pyupgrade (modern syntax for the target version)
  - `B` — flake8-bugbear (likely bugs and foot-guns)

## Layout

- **4-space indentation.** Never tabs.
- **Line length: 100 columns** (matches ruff). Let the formatter wrap; do not add manual
  backslash continuations.
- One statement per line; one blank line between methods, two between top-level defs.
- Files are UTF-8, end with a single trailing newline.

## Naming

| Kind | Convention | Example |
|---|---|---|
| Modules / packages | `snake_case` (short) | `token_store.py` |
| Functions / methods | `snake_case` | `get_contacts()` |
| Variables | `snake_case` | `tenant_id` |
| Classes | `PascalCase` | `FileTokenStore` |
| Constants | `UPPER_SNAKE_CASE` | `PROVIDER_SCOPES` |
| Type variables | `PascalCase` (short) | `T`, `ModelT` |

`N` (pep8-naming) enforces these. Do not prefix with `_` for "private" unless it is a real
implementation detail; a leading underscore is a contract, not decoration.

## Imports

- **Three groups, in this order, separated by a blank line:** standard library, then
  third-party, then first-party/local (`app...`). isort (`I`) enforces and auto-sorts.
- **One import per line.** `import os` then `import sys` — not `import os, sys`.
- Prefer absolute imports (`from app.<provider>.service import ProviderService`) over relative.
- No wildcard imports (`from x import *`) — they defeat `F` and hide names.

```python
from __future__ import annotations

import logging
from datetime import date

import httpx
from fastapi import APIRouter, Depends

from app.config import Settings
from app.provider.service import ProviderService
```

## Type hints

- **Required on every public function/method** — all parameters and the return type.
- **Use `X | None`, not `Optional[X]`; use `list[str]`, not `List[str]`.** The target is
  Python 3.14, so modern built-in generics and union syntax are standard (`UP` enforces).
- Annotate module-level constants and non-obvious locals where it aids the reader.
- Prefer precise types (`date`, `Decimal`) over `Any`. Reach for `Any` only at genuinely
  dynamic boundaries (e.g. passthrough of unmodelled provider payload fields), and comment why.

## Docstrings

- **Module docstring** at the top of every module: one line saying what the module is for.
- **Public functions, classes, and methods carry a docstring.** Triple-quoted `"""..."""`,
  first line an imperative summary (`"Return the org's contacts."`), no blank line before it.
- Keep them short. A one-line docstring is fine for a small helper; expand only when the
  contract (params, raised errors, side effects) is non-obvious.
- Private one-liners may skip a docstring if the name and signature are self-explanatory.

```python
"""Provider API wrapper: tenant injection, pagination, error mapping."""


def get_contact(contact_id: str) -> Contact | None:
    """Return a single contact by id, or None if the provider has no such contact."""
    ...
```

## Functions and control flow

- **Small and single-purpose.** If a function needs an "and" to describe it, split it.
- Prefer early returns / guard clauses over deep nesting.
- **Never use a bare `except:`.** Catch the narrowest exception you can
  (`except httpx.HTTPStatusError:`); re-raise or wrap with context. `except Exception:` is
  allowed only at a top-level boundary where you log and convert to a response.
- Do not silently swallow errors — at minimum log with enough context to diagnose.
- No mutable default arguments (`def f(items: list = [])`) — `B` flags this; use `None` and
  build inside.

## Comments

- Comment **why**, not what. The code already says what it does.
- Delete commented-out code; version control remembers it.
- Keep `# TODO:` notes actionable and, where possible, tied to a tracked issue.

## The PostToolUse hook (see `.claude/settings.json`)

The shared config ships a conservative `PostToolUse` hook that runs `uv run ruff format` then
`uv run ruff check --fix` after `Edit`/`Write`/`MultiEdit`, so committed code stays formatted
and lint-clean without anyone remembering to run it. It is written to **never hard-fail the
edit** — if `uv`/`ruff` is not installed it exits cleanly and does nothing. Note: this hook is
a **human-developer / devcontainer** convenience and does **not** run inside a managed-agent
session, so **CI is the authoritative enforcement** for agent-authored code.
