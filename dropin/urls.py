from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="dropin_index"),
    path("login/", views.DropInLoginView.as_view(), name="dropin_login"),
    path("logout/", views.DropInLogoutView.as_view(), name="dropin_logout"),
    path("register/", views.register_wizard, {"step": "account"}, name="dropin_register"),
    path("register/<slug:step>/", views.register_wizard, name="dropin_register"),
    path("dashboard/", views.dashboard, name="dropin_dashboard"),
    path("book/", views.book, name="dropin_book"),
    path("booking/success/", views.booking_success, name="dropin_booking_success"),
    path("roster/", views.daily_roster, name="dropin_roster"),
]
