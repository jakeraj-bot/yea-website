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


def mark_contact_form_started(request):
    request.session[CONTACT_FORM_SESSION_KEY] = time.time()
    request.session.modified = True


def contact_form_started_at(request):
    return request.session.get(CONTACT_FORM_SESSION_KEY)


def _contact_rate_key(request):
    ip = get_client_ip(request)
    if ip:
        return f"contact-submit:{ip}"
    session_key = getattr(request.session, "session_key", None)
    if session_key:
        return f"contact-submit:session:{session_key}"
    return ""


def is_contact_rate_limited(request):
    cache_key = _contact_rate_key(request)
    if not cache_key:
        return False
    limit = getattr(settings, "CONTACT_FORM_RATE_LIMIT", 5)
    count = cache.get(cache_key, 0)
    return count >= limit


def record_contact_submission(request):
    cache_key = _contact_rate_key(request)
    if not cache_key:
        return
    window = getattr(settings, "CONTACT_FORM_RATE_WINDOW_SECONDS", 3600)
    count = cache.get(cache_key, 0) + 1
    cache.set(cache_key, count, window)


def is_contact_form_too_fast(request):
    started = contact_form_started_at(request)
    if not started:
        return False
    min_seconds = getattr(settings, "CONTACT_FORM_MIN_SECONDS", 3)
    max_seconds = getattr(settings, "CONTACT_FORM_MAX_SECONDS", 7200)
    elapsed = time.time() - float(started)
    return elapsed < min_seconds or elapsed > max_seconds


def is_honeypot_triggered(cleaned_data):
    return bool((cleaned_data.get("company") or "").strip())


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
