from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("portals/", RedirectView.as_view(pattern_name="portal_home", permanent=False), name="portals"),
    path("about/", views.our_story, name="our_story"),
    path("about/meet-the-staff/", views.meet_the_staff, name="meet_the_staff"),
    path("contact/", views.contact, name="contact"),
    path("safety/", views.safety, name="safety"),
]
