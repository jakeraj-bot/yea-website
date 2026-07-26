from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.our_story, name="our_story"),
    path("about/meet-the-staff/", views.meet_the_staff, name="meet_the_staff"),
    path("contact/", views.contact, name="contact"),
    path("safety/", views.safety, name="safety"),
]
