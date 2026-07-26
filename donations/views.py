from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from core import photos

from . import giving
from .stripe_checkout import create_checkout_session


def index(request):
    context = {
        "gallery_photos": photos.DONATE_GALLERY,
        "giving_cards": giving.GIVING_CARDS,
        "min_gift": giving.MIN_GIFT,
        "stripe_configured": bool(settings.STRIPE_SECRET_KEY),
    }
    if request.GET.get("success") == "1":
        context["donation_success"] = True
    if request.GET.get("canceled") == "1":
        context["donation_canceled"] = True
    return render(request, "donations/index.html", context)


@require_http_methods(["POST"])
def checkout(request):
    try:
        session = create_checkout_session(request, request.POST)
        return redirect(session.url, code=303)
    except RuntimeError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Unable to start checkout: {exc}")
    return redirect("donate")
