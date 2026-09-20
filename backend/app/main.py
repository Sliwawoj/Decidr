from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router
from app.core.config import Settings
from app.core.errors import DomainError
from app.db.session import create_database
from app.scheduler import start_scheduler
from app.services.analyzer import LLMAnalyzer
from app.services.demo import load_demo
from app.services.gmail import GmailService
from app.services.ingestion import IngestionService
from app.services.push import PushService


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _loopback_twin(origin: str) -> str | None:
    parts = urlsplit(origin)
    host = (parts.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1"}:
        return None
    alt = "127.0.0.1" if host == "localhost" else "localhost"
    netloc = f"{alt}:{parts.port}" if parts.port else alt
    return _normalize_origin(f"{parts.scheme}://{netloc}")


def _allowed_origins(request: Request, frontend_url: str) -> set[str]:
    """FRONTEND_URL plus the Host this request actually hit (nginx / ngrok)."""
    allowed = {_normalize_origin(frontend_url)}
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[
        0
    ].strip()
    if host:
        proto = (
            request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        ).split(",")[0].strip()
        if proto not in {"http", "https"}:
            proto = "http"
        allowed.add(_normalize_origin(f"{proto}://{host}"))
        # TLS often terminates at the tunnel while nginx sees http.
        other = "https" if proto == "http" else "http"
        allowed.add(_normalize_origin(f"{other}://{host}"))
    expanded: set[str] = set()
    for item in allowed:
        expanded.add(item)
        twin = _loopback_twin(item)
        if twin:
            expanded.add(twin)
    return expanded


def origin_allowed(request: Request, frontend_url: str) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    return _normalize_origin(origin) in _allowed_origins(request, frontend_url)


def create_app(settings: Settings | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = create_database(settings)
        app.state.settings = settings
        app.state.sessions = sessions
        app.state.login_attempts = {}
        app.state.gmail = GmailService(settings, sessions)
        app.state.push = PushService(settings, sessions)
        app.state.ingestion = IngestionService(
            settings, sessions, LLMAnalyzer(settings), app.state.gmail, app.state.push
        )
        if settings.app_mode == "demo" and settings.demo_autoload:
            with sessions() as session:
                load_demo(session, app.state.ingestion)
        scheduler = start_scheduler(settings, app.state.ingestion)
        yield
        if scheduler:
            scheduler.shutdown(wait=True)
        engine.dispose()

    app = FastAPI(title="Decidr API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        https_only=settings.cookie_secure,
        same_site="lax",
        max_age=8 * 3600,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Decidr-Client"],
    )

    @app.middleware("http")
    async def protect_mutations(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            if request.headers.get("X-Decidr-Client") != "web":
                return JSONResponse({"detail": "Brak nagłówka klienta."}, status_code=403)
            if not origin_allowed(request, settings.frontend_url):
                return JSONResponse({"detail": "Niedozwolone źródło żądania."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    app.include_router(router)
    return app


app = create_app()