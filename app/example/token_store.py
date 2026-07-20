"""Persistence for the provider auth token dict (including any rotating refresh token).

The token dict is opaque: whatever the auth layer hands us is JSON round-tripped
verbatim. We make no assumptions about its keys.

Extension seam
--------------
``TokenStore`` is an ABC so the backend is pluggable. ``FileTokenStore`` writes JSON
to a path injected via its constructor (never imported from settings), so a future
secret-manager / environment / database backend can implement the same interface and
be selected via config **without touching any call site**. Callers depend on the
``TokenStore`` contract (``load`` / ``save``) only.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


class TokenStore(ABC):
    """Backend-agnostic persistence contract for the provider auth token dict."""

    @abstractmethod
    def load(self) -> dict | None:
        """Return the persisted token dict, or None if nothing is stored."""

    @abstractmethod
    def save(self, token: dict) -> None:
        """Persist the token dict, overwriting any previous value."""


class FileTokenStore(TokenStore):
    """Store the token dict as JSON on the local filesystem.

    A rotating refresh token is overwritten on every refresh, so writes are
    atomic: the payload is written to a temporary file in the same directory and
    then ``os.replace``-d onto the target. A crash mid-write can never leave a
    truncated or corrupt token file — the target is either the old value or the
    fully-written new one.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> dict | None:
        """Read the token dict from disk; return None if the file does not exist."""
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return None

    def save(self, token: dict) -> None:
        """Atomically write the token dict as JSON, creating parent dirs as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=self._path.name, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(token, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self._path)
        except BaseException:
            # Never leave a stray temp file behind on failure.
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
