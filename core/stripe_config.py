from django.conf import settings

# Keep Checkout under Gunicorn's request window so a hung Stripe call
# returns a parent-facing error instead of Render 502.
STRIPE_HTTP_TIMEOUT_SECONDS = 20


def donation_stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLIC_KEY)


def member_stripe_configured():
    return bool(settings.MEMBER_STRIPE_SECRET_KEY and settings.MEMBER_STRIPE_PUBLIC_KEY)


def member_stripe_is_test_mode():
    """True only when member Stripe keys are explicitly test-mode. Live keys never qualify."""
    secret = (getattr(settings, "MEMBER_STRIPE_SECRET_KEY", None) or "").strip()
    public = (getattr(settings, "MEMBER_STRIPE_PUBLIC_KEY", None) or "").strip()
    return secret.startswith("sk_test_") and public.startswith("pk_test_")


def _configure_stripe(stripe_module, api_key):
    stripe_module.api_key = api_key
    stripe_module.max_network_retries = 1
    try:
        requests_client = getattr(stripe_module.http_client, "RequestsClient", None)
        if requests_client:
            stripe_module.default_http_client = requests_client(timeout=STRIPE_HTTP_TIMEOUT_SECONDS)
    except Exception:
        pass
    return stripe_module


def donation_stripe():
    import stripe

    return _configure_stripe(stripe, settings.STRIPE_SECRET_KEY)


def member_stripe():
    import stripe

    return _configure_stripe(stripe, settings.MEMBER_STRIPE_SECRET_KEY)
