from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="donate"),
    path("checkout/", views.checkout, name="donate_checkout"),
]
