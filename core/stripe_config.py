from django.conf import settings


def donation_stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLIC_KEY)


def member_stripe_configured():
    return bool(settings.MEMBER_STRIPE_SECRET_KEY and settings.MEMBER_STRIPE_PUBLIC_KEY)


def donation_stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def member_stripe():
    import stripe

    stripe.api_key = settings.MEMBER_STRIPE_SECRET_KEY
    return stripe
