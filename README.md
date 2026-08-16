# GoreeCloud Calendar

GoreeCloud Calendar is the native GoreeCloud calendar application. It provides a privacy-first, self-hosted web interface over the authoritative GoreeCloud CalDAV service.

## Architecture

- User-facing application: `https://calendar.goreecloud.com`
- Authoritative CalDAV service: `https://dav.goreecloud.com`
- Calendar data remains authoritative in Radicale/CalDAV. GoreeCloud Calendar does not maintain a competing calendar database.
- CalDAV credentials stay server-side and are supplied through environment configuration; they are never embedded in browser assets.

## Current foundation

The initial application provides:

- FastAPI backend and health endpoint
- server-side CalDAV discovery and event retrieval
- bounded upstream timeouts and fail-closed configuration
- normalized event API for the browser
- responsive Glaze UI month/agenda experience
- System, Light, and Dark appearance modes stored locally in the browser
- accessible keyboard/focus treatment and reduced-motion support
- Docker/Compose development packaging
- automated backend tests and GitHub Actions CI

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000`.

## Safety

The current foundation is read-only. Event mutation is intentionally not implemented until CalDAV write semantics, ETag/precondition conflict handling, multi-user isolation, backup/recovery, and production acceptance are validated.

## License

AGPL-3.0-only.
