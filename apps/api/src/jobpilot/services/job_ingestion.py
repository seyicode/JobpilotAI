"""Normalisation used to detect duplicate job postings. No network access."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that track clicks rather than identify a posting.
_TRACKING_PARAMS = re.compile(
    r"^(utm_.*|ref|refid|referrer|source|src|trk|trackingid|gclid|fbclid|mc_[a-z]+|_hs[a-z]+)$",
    re.IGNORECASE,
)


class InvalidJobUrl(ValueError):
    """The URL is not an http(s) URL. Messages are safe to show users."""


def description_fingerprint(description: str) -> str:
    """Hash of the description ignoring case, whitespace, and punctuation differences."""
    normalized = re.sub(r"[^\w]+", " ", description.lower()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def canonical_url(url: str) -> str:
    """Treat http and https alike; lowercase the host; drop www, fragments, tracking
    parameters, and trailing slashes; sort remaining query parameters."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise InvalidJobUrl("Job URLs must start with http:// or https://.")
    host = parts.hostname.lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
               if not _TRACKING_PARAMS.match(k))
    )
    path = parts.path.rstrip("/") or ""
    return urlunsplit(("https", host, path, query, ""))
