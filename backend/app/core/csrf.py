"""Same-origin mutation guard helpers."""

from urllib.parse import urlsplit

from fastapi import Request


def _normalize(origin: str) -> str:
    return origin.strip().rstrip("/")


def _swap_loopback(origin: str) -> str | None:
    """localhost and 127.0.0.1 are interchangeable in local browser URLs."""
    parts = urlsplit(origin)
    host = (parts.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1"}:
        return None
    alt = "127.0.0.1" if host == "localhost" else "localhost"
    netloc = f"{alt}:{parts.port}" if parts.port else alt
    return _normalize(f"{parts.scheme}://{netloc}")


def public_base_url(request: Request, fallback: str) -> str:
    """URL the browser is using (localhost or ngrok), not a fixed FRONTEND_URL."""
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[
        0
    ].strip()
    if not host:
        return _normalize(fallback)
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if proto not in {"http", "https"}:
        hostname = host.split(":")[0].lower()
        if hostname in {"localhost", "127.0.0.1"}:
            proto = "http"
        elif fallback.lower().startswith("https://"):
            proto = "https"
        else:
            proto = request.url.scheme or "http"
    return _normalize(f"{proto}://{host}")


def allowed_origins(request: Request, frontend_url: str) -> set[str]:
    allowed = {_normalize(frontend_url)}
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[
        0
    ].strip()
    if host:
        proto = (
            request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        ).split(",")[0].strip()
        if proto not in {"http", "https"}:
            proto = "http"
        allowed.add(_normalize(f"{proto}://{host}"))
        # TLS often terminates at ngrok/CDN while the app sees http — accept both.
        other = "https" if proto == "http" else "http"
        allowed.add(_normalize(f"{other}://{host}"))

    expanded: set[str] = set()
    for origin in allowed:
        expanded.add(origin)
        swapped = _swap_loopback(origin)
        if swapped:
            expanded.add(swapped)
    return expanded


def origin_allowed(request: Request, frontend_url: str) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    return _normalize(origin) in allowed_origins(request, frontend_url)
