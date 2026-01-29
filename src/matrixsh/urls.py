"""URL helpers.

MatrixShell talks to MatrixLLM in two "namespaces":

- OpenAI-compatible API endpoints under /v1 (e.g. /v1/chat/completions)
- Gateway/admin endpoints at the server root (e.g. /health, /pair/info)

Users frequently configure either:

- http://127.0.0.1:11435
- http://127.0.0.1:11435/v1

Historically MatrixShell used naive string replacement of "/v1" which breaks
when the URL is missing that suffix (or contains it in an unexpected place).
These helpers normalize URLs and make the intent explicit.
"""

from __future__ import annotations

from urllib.parse import urlparse


def _ensure_scheme(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    # Allow "localhost:11435" style inputs.
    if "://" not in url:
        return "http://" + url
    return url


def root_url(base_url: str) -> str:
    """Return the server root URL: scheme://host:port

    Any path component is discarded intentionally because MatrixLLM's health and
    pairing endpoints live at the root.
    """
    u = urlparse(_ensure_scheme(base_url))
    scheme = u.scheme or "http"
    netloc = u.netloc or u.path  # handle edge cases where netloc is empty
    return f"{scheme}://{netloc}".rstrip("/")


def api_base_url(base_url: str) -> str:
    """Return a normalized OpenAI-compatible base url that ends with /v1."""
    r = root_url(base_url)
    return f"{r}/v1"
