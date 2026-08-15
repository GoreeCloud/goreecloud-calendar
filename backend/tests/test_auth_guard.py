import pytest

from app.auth_guard import LoginBlocked, LoginRateLimiter


def test_login_limiter_blocks_after_configured_failures():
    limiter = LoginRateLimiter(max_failures=2, window_seconds=60, lockout_seconds=120)
    limiter.failure(" person ")
    limiter.failure("person")

    with pytest.raises(LoginBlocked) as exc_info:
        limiter.check("PERSON")

    assert exc_info.value.retry_after_seconds > 0


def test_login_limiter_success_clears_failures():
    limiter = LoginRateLimiter(max_failures=2, window_seconds=60, lockout_seconds=120)
    limiter.failure("person")
    limiter.success("person")
    limiter.check("person")
