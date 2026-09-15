from django.conf import settings


def donation_stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLIC_KEY)


def member_stripe_configured():
    return bool(settings.MEMBER_STRIPE_SECRET_KEY and settings.MEMBER_STRIPE_PUBLIC_KEY)


def member_stripe_is_test_mode():
    """True only when member Stripe keys are explicitly test-mode. Live keys never qualify."""
    secret = (getattr(settings, "MEMBER_STRIPE_SECRET_KEY", None) or "").strip()
    public = (getattr(settings, "MEMBER_STRIPE_PUBLIC_KEY", None) or "").strip()
    return secret.startswith("sk_test_") and public.startswith("pk_test_")


def donation_stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def member_stripe():
    import stripe

    stripe.api_key = settings.MEMBER_STRIPE_SECRET_KEY
    return stripe
