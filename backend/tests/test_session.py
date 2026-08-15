from datetime import datetime, timezone

from app.session import SessionStore


def test_session_store_uses_opaque_tokens_and_retains_credentials_server_side():
    store = SessionStore(60, idle_seconds=30)
    record = store.create(username=" person ", password="secret")

    assert record.username == "person"
    assert record.password == "secret"
    assert record.token != "secret"
    assert record.csrf_token != record.token
    assert record.expires_at > datetime.now(timezone.utc)
    assert store.get(record.token) is not None


def test_session_delete_revokes_token():
    store = SessionStore(60)
    record = store.create(username="person", password="secret")
    store.delete(record.token)
    assert store.get(record.token) is None


def test_session_store_enforces_per_user_limit():
    store = SessionStore(60, max_total=10, max_per_user=2)
    first = store.create(username="person", password="secret")
    second = store.create(username="person", password="secret")
    third = store.create(username="person", password="secret")

    assert store.get(first.token, touch=False) is None
    assert store.get(second.token, touch=False) is not None
    assert store.get(third.token, touch=False) is not None
    assert store.count() == 2


def test_session_store_enforces_global_limit():
    store = SessionStore(60, max_total=2, max_per_user=2)
    first = store.create(username="one", password="secret")
    store.create(username="two", password="secret")
    store.create(username="three", password="secret")

    assert store.get(first.token, touch=False) is None
    assert store.count() == 2
