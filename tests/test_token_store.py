"""FileTokenStore persistence and atomic-overwrite invariant.

A rotating refresh token is overwritten on every refresh, so the store must
fully *overwrite* — never merge or append — and leave no temp files behind.
These tests pin that behaviour on a throwaway ``tmp_path``.
"""

from app.example.token_store import FileTokenStore


def test_load_is_none_before_save(tmp_path) -> None:
    store = FileTokenStore(tmp_path / "example_token.json")
    assert store.load() is None


def test_save_then_load_roundtrips(tmp_path) -> None:
    store = FileTokenStore(tmp_path / "example_token.json")
    token = {"access_token": "at1", "refresh_token": "rt1", "expires_in": 1800}
    store.save(token)
    assert store.load() == token


def test_second_save_overwrites(tmp_path) -> None:
    path = tmp_path / "example_token.json"
    store = FileTokenStore(path)

    store.save({"access_token": "at1", "refresh_token": "rt1"})
    store.save({"access_token": "at2", "refresh_token": "rt2"})

    loaded = store.load()
    assert loaded is not None
    # Full overwrite: the store never merges old and new tokens.
    assert loaded == {"access_token": "at2", "refresh_token": "rt2"}


def test_atomic_overwrite_leaves_no_temp_files(tmp_path) -> None:
    path = tmp_path / "example_token.json"
    store = FileTokenStore(path)

    store.save({"refresh_token": "rt1"})
    store.save({"refresh_token": "rt2"})

    # os.replace onto the target + temp cleanup => exactly one file remains.
    assert list(tmp_path.iterdir()) == [path]
