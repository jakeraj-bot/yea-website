from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.email_service import send_site_email

from . import photos
from .forms import ContactForm
from .models import ContactMessage
from .spam_protection import (
    CONTACT_FORM_SESSION_KEY,
    is_contact_form_too_fast,
    is_contact_rate_limited,
    is_honeypot_triggered,
    mark_contact_form_started,
    record_contact_submission,
    turnstile_enabled,
    verify_turnstile,
    get_client_ip,
)

ENROLLMENT_FLYER_CANDIDATES = (
    "images/site/enrollment-flyer.jpg",
    "images/site/enrollment-flyer.jpeg",
    "images/site/enrollment-flyer.png",
    "images/site/enrollment-flyer.webp",
)


def enrollment_flyer_static_path():
    for name in ENROLLMENT_FLYER_CANDIDATES:
        if find(name):
            return name
    return ""


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "gallery_photos": photos.HOME_GALLERY,
            "school_18_photo": photos.SCHOOL_18_FEATURED,
            "dale_ave_photo": photos.DALE_AVE_FEATURED,
            "enrollment_flyer": enrollment_flyer_static_path(),
        },
    )


def our_story(request):
    founders = [
        {
            "name": "Jakera Jacobs",
            "title": "Co-Founder & Co-CEO",
            "bio": (
                "Co-Founder and Co-CEO Jakera Jacobs leads YEA's internal operations, finance, "
                "human resources, and compliance. With more than 19 years in youth development "
                "and educational programming, she has managed school-based and federally funded "
                "initiatives, including as Project Director for the Nita M. Lowey 21st Century "
                "Community Learning Centers (21st CCLC) program. She specializes in fiscal "
                "management, organizational systems, multi-site operations, and regulatory "
                "compliance. She holds an MBA in Accounting from William Paterson University, a "
                "New Jersey Certificate of Eligibility for School Business Administrator, and is "
                "pursuing a Doctorate in Educational Leadership (Ed.D.). Her leadership "
                "strengthens YEA's capacity to deliver innovative, high-quality programs for "
                "youth and families across Northern New Jersey."
            ),
        },
        {
            "name": "Janice Gomez",
            "title": "Co-Founder & Co-CEO",
            "bio": (
                "Janice Gomez brings executive insight and a legacy of transformative leadership "
                "to the Passaic community. A former leader within the Full Service Community "
                "Schools (FSCS) model, she opened, developed, and staffed programs at Passaic "
                "School No. 6 and Passaic High School from the ground up — giving her intimate "
                "knowledge of each site's infrastructure, faculty, and community dynamics. She "
                "modernized operations at these sites, moving beyond traditional childcare to the "
                "forward-thinking enrichment standards YEA champions today. Her proven ability "
                "to scale programs from day one helps ensure immediate stability as YEA grows."
            ),
        },
    ]
    return render(request, "core/our_story.html", {"founders": founders})


def meet_the_staff(request):
    staff = [
        {
            "name": "Jahmir Graham",
            "title": "Outreach Manager",
            "focus": "Building connections between YEA and the communities we serve.",
        },
        {
            "name": "Karla Decena",
            "title": "Assistant to Co-CEO",
            "focus": "Supporting day-to-day operations and executive coordination.",
        },
        {
            "name": "Llajaira Nieves",
            "title": "Director, School 18",
            "focus": "Overseeing daily program operations and staff at School 18.",
        },
        {
            "name": "Shakim Adams",
            "title": "Youth Counselor",
            "focus": "Mentoring students and creating a safe after-school environment.",
        },
        {
            "name": "Caron Jacobs",
            "title": "AmeriCorps Counselor",
            "focus": "Providing academic support through AmeriCorps service.",
        },
        {
            "name": "Alisha Guzman",
            "title": "AmeriCorps Counselor",
            "focus": "Delivering hands-on learning and student mentorship.",
        },
        {
            "name": "Quisaan Jacobs",
            "title": "Director Floater",
            "focus": "Supporting program continuity across YEA campuses.",
        },
        {
            "name": "Jordyn Jacobs-Lee",
            "title": "Social Media Intern",
            "focus": "Engaging our community through social media storytelling.",
        },
    ]
    return render(request, "core/meet_the_staff.html", {"staff": staff})


def _send_contact_notification(contact):
    topic_label = contact.get_topic_display()
    subject = f"[YEA Website] {topic_label} — {contact.name}"
    body = (
        f"Name: {contact.name}\n"
        f"Email: {contact.email}\n"
        f"Topic: {topic_label}\n\n"
        f"Message:\n{contact.message}\n"
    )
    send_site_email(
        subject=subject,
        message=body,
        recipient_list=[settings.CONTACT_EMAIL],
        reply_to=[contact.email],
    )


def _contact_success_redirect():
    return redirect(f"{reverse('contact')}?sent=1")


@require_http_methods(["GET", "POST"])
def contact(request):
    form = ContactForm()
    submitted = request.GET.get("sent") == "1"

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            if is_contact_rate_limited(request):
                form.add_error(
                    None,
                    "Too many messages were sent from your connection. Please wait an hour and try again, or email info@yeanj.org directly.",
                )
            elif is_honeypot_triggered(form.cleaned_data) or is_contact_form_too_fast(request):
                if CONTACT_FORM_SESSION_KEY in request.session:
                    del request.session[CONTACT_FORM_SESSION_KEY]
                return _contact_success_redirect()
            elif turnstile_enabled() and not verify_turnstile(
                request.POST.get("cf-turnstile-response"),
                get_client_ip(request),
            ):
                form.add_error(
                    None,
                    "Please complete the security check and try again.",
                )
            else:
                contact_message = ContactMessage.objects.create(
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    topic=form.cleaned_data["topic"],
                    message=form.cleaned_data["message"],
                )
                _send_contact_notification(contact_message)
                record_contact_submission(request)
                if CONTACT_FORM_SESSION_KEY in request.session:
                    del request.session[CONTACT_FORM_SESSION_KEY]
                return _contact_success_redirect()
    else:
        mark_contact_form_started(request)

    return render(
        request,
        "core/contact.html",
        {
            "form": form,
            "submitted": submitted,
            "turnstile_site_key": settings.TURNSTILE_SITE_KEY if turnstile_enabled() else "",
        },
    )


def safety(request):
    return render(request, "core/safety.html")
