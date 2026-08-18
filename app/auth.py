from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from secrets import token_urlsafe
from threading import RLock
from time import monotonic, sleep

from fastapi import HTTPException, Request, Response, status

from .caldav import CalDAVClient, CalDAVError
from .config import Settings

SESSION_COOKIE = "goreecloud_calendar_session"


@dataclass
class Session:
    username: str
    password: str
    csrf_token: str
    expires_at: float


class SessionStore:
    def __init__(self, ttl_seconds: int, max_sessions: int):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()

    def _prune(self) -> None:
        now = monotonic()
        expired = [key for key, value in self._sessions.items() if value.expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)

    def create(self, username: str, password: str) -> tuple[str, Session]:
        with self._lock:
            self._prune()
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions, key=lambda key: self._sessions[key].expires_at)
                self._sessions.pop(oldest, None)
            session_id = token_urlsafe(32)
            session = Session(
                username=username,
                password=password,
                csrf_token=token_urlsafe(32),
                expires_at=monotonic() + self.ttl_seconds,
            )
            self._sessions[session_id] = session
            return session_id, session

    def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        with self._lock:
            self._prune()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.expires_at = monotonic() + self.ttl_seconds
            return session

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)


async def authenticate(settings: Settings, store: SessionStore, username: str, password: str) -> tuple[str, Session]:
    if not username or not password or len(username) > 254 or len(password) > 1024:
        sleep(0.25)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    client = CalDAVClient(settings, (username, password))
    try:
        await client.list_calendars()
    except CalDAVError as exc:
        sleep(0.25)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc
    return store.create(username, password)


def set_session_cookie(response: Response, settings: Settings, session_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="strict",
    )


def require_session(request: Request, store: SessionStore) -> Session:
    session = store.get(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return session


def require_csrf(request: Request, session: Session) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request verification failed")
