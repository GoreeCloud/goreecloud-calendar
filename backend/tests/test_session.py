from datetime import datetime, timezone

from app.session import SessionStore


def test_session_store_uses_opaque_tokens_and_retains_credentials_server_side():
    store = SessionStore(60)
    record = store.create(username=" person ", password="secret")

    assert record.username == "person"
    assert record.password == "secret"
    assert record.token != "secret"
    assert record.csrf_token != record.token
    assert record.expires_at > datetime.now(timezone.utc)
    assert store.get(record.token) == record


def test_session_delete_revokes_token():
    store = SessionStore(60)
    record = store.create(username="person", password="secret")
    store.delete(record.token)
    assert store.get(record.token) is None
