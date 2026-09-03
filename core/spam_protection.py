"""Lightweight anti-spam helpers for public forms."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CONTACT_FORM_SESSION_KEY = "contact_form_started_at"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def cache_key_for_request(request, prefix):
    ip = get_client_ip(request)
    if ip:
        return f"{prefix}:{ip}"
    session_key = getattr(request.session, "session_key", None)
    if session_key:
        return f"{prefix}:session:{session_key}"
    return ""


def is_rate_limited(request, prefix, limit, window_seconds):
    cache_key = cache_key_for_request(request, prefix)
    if not cache_key:
        return False
    return cache.get(cache_key, 0) >= limit


def record_attempt(request, prefix, window_seconds):
    cache_key = cache_key_for_request(request, prefix)
    if not cache_key:
        return
    cache.set(cache_key, cache.get(cache_key, 0) + 1, window_seconds)


def mark_form_started(request, session_key, *, refresh=True):
    if not refresh and request.session.get(session_key):
        return
    request.session[session_key] = time.time()
    request.session.modified = True


def is_form_too_fast(request, session_key, min_seconds=3, max_seconds=None):
    started = request.session.get(session_key)
    if not started:
        return True
    elapsed = time.time() - float(started)
    if elapsed < min_seconds:
        return True
    if max_seconds is not None and elapsed > max_seconds:
        return True
    return False


def mark_contact_form_started(request):
    mark_form_started(request, CONTACT_FORM_SESSION_KEY)


def contact_form_started_at(request):
    return request.session.get(CONTACT_FORM_SESSION_KEY)


def _contact_rate_key(request):
    return cache_key_for_request(request, "contact-submit")


def is_contact_rate_limited(request):
    limit = getattr(settings, "CONTACT_FORM_RATE_LIMIT", 5)
    window = getattr(settings, "CONTACT_FORM_RATE_WINDOW_SECONDS", 3600)
    return is_rate_limited(request, "contact-submit", limit, window)


def record_contact_submission(request):
    window = getattr(settings, "CONTACT_FORM_RATE_WINDOW_SECONDS", 3600)
    record_attempt(request, "contact-submit", window)


def is_contact_form_too_fast(request):
    min_seconds = getattr(settings, "CONTACT_FORM_MIN_SECONDS", 3)
    max_seconds = getattr(settings, "CONTACT_FORM_MAX_SECONDS", 7200)
    started = contact_form_started_at(request)
    if not started:
        return False
    elapsed = time.time() - float(started)
    return elapsed < min_seconds or elapsed > max_seconds


def is_honeypot_triggered(cleaned_data):
    if not cleaned_data:
        return False
    return bool(
        (cleaned_data.get("company") or "").strip()
        or (cleaned_data.get("website") or "").strip()
    )


def turnstile_enabled():
    return bool(
        getattr(settings, "TURNSTILE_SITE_KEY", "")
        and getattr(settings, "TURNSTILE_SECRET_KEY", "")
    )


def verify_turnstile(token, remote_ip=None):
    if not turnstile_enabled():
        return True
    if not token:
        return False
    payload = urllib.parse.urlencode(
        {
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": token,
            "remoteip": remote_ip or "",
        }
    ).encode()
    request = urllib.request.Request(
        TURNSTILE_VERIFY_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        logger.exception("Turnstile verification failed")
        return False
    return bool(data.get("success"))
