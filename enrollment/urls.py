from django.urls import path

from . import views

urlpatterns = [
    path("policies/<slug:slug>/", views.policy_detail, name="enrollment_policy"),
    path("confirmation/<uuid:reference>/", views.confirmation, name="enrollment_confirmation"),
    path("confirmation/group/<uuid:family_group>/", views.confirmation_group, name="enrollment_confirmation_group"),
    path("print/<uuid:reference>/", views.print_application, name="enrollment_print"),
    path("", views.apply_wizard, {"step": "family"}, name="apply"),
    path("<slug:step>/", views.apply_wizard, name="enrollment_apply"),
]
