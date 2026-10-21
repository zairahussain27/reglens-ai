"""Fetch a remote regulation with SSRF protection (no private / loopback / link-local targets)."""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from ..config import get_settings

settings = get_settings()
ALLOWED_TYPES = ("application/pdf", "text/html", "text/plain", "application/xhtml+xml")


def _check_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(422, "Enter a valid http(s) URL")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise HTTPException(422, "Could not resolve that website")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(422, "That address is not allowed")


def fetch(url: str) -> tuple[bytes, str, str]:
    """Return (bytes, content_type, suggested_filename). Follows up to 4 redirects, re-validating each hop."""
    headers = {"User-Agent": "RegLensBot/1.0 (+compliance research)"}
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        for _ in range(5):
            _check_host(url)
            try:
                with client.stream("GET", url) as r:
                    if r.is_redirect and r.headers.get("location"):
                        url = str(httpx.URL(url).join(r.headers["location"]))
                        continue
                    if r.status_code >= 400:
                        raise HTTPException(422, f"The website returned an error ({r.status_code})")
                    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype and not ctype.startswith(ALLOWED_TYPES):
                        raise HTTPException(415, "Only PDF, HTML or text pages can be imported")
                    data = bytearray()
                    for part in r.iter_bytes():
                        data.extend(part)
                        if len(data) > settings.max_upload_bytes:
                            raise HTTPException(413, f"The page is larger than {settings.max_upload_mb} MB")
                    name = urlparse(url).path.rsplit("/", 1)[-1] or "regulation"
                    if ctype == "application/pdf" and not name.lower().endswith(".pdf"):
                        name += ".pdf"
                    elif ctype.startswith("text/html") and not name.lower().endswith((".html", ".htm")):
                        name += ".html"
                    return bytes(data), ctype, name
            except httpx.HTTPError as exc:
                raise HTTPException(422, f"Could not download that URL ({type(exc).__name__})")
    raise HTTPException(422, "Too many redirects")
