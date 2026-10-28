"""Shared request helpers: errors, owner identity, rate limiting, JSON bodies."""
import re
import time
from collections import defaultdict, deque

from flask import current_app, request
from pydantic import ValidationError

OWNER_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message, self.status, self.details = message, status, details


def owner_id() -> str:
    oid = request.headers.get("X-Owner-Id", "").strip()
    if not OWNER_RE.match(oid):
        raise ApiError("Missing or invalid owner id.", 401)
    return oid


def json_body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def validation_details(exc: ValidationError):
    return [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()[:10]]


def parse(model_cls, data, message="Some fields are invalid."):
    """Validate client data against a Pydantic model and raise a 422 with field details."""
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ApiError(message, 422, validation_details(exc))


def init_limiter(app):
    app.extensions["tv_limiter"] = {"hits": defaultdict(deque), "global": deque()}


def check_rate_limit(oid: str):
    """Every AI call goes through this. Protects the API key from abuse."""
    lim = current_app.extensions["tv_limiter"]
    now = time.time()
    per_user = lim["hits"][(oid, request.remote_addr)]
    for q, limit in ((per_user, current_app.config["RATE_LIMIT_PER_HOUR"]),
                     (lim["global"], current_app.config["GLOBAL_LIMIT_PER_HOUR"])):
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= limit:
            raise ApiError("Too many AI requests. Please wait a while and try again.", 429)
    per_user.append(now)
    lim["global"].append(now)


def one_of(value, allowed, field):
    if value not in allowed:
        raise ApiError(f"{field} must be one of: {', '.join(allowed)}.", 400)
    return value


def clean_url(value, field="url"):
    from urllib.parse import urlparse
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip()
    u = urlparse(v)
    if u.scheme not in ("http", "https") or not u.netloc or len(v) > 300 or " " in v:
        raise ApiError(f"{field} must be a valid http(s) link.", 422)
    return v
