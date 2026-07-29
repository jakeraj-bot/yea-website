from django.urls import path

from . import views

urlpatterns = [
    path("policies/<slug:slug>/", views.policy_detail, name="enrollment_policy"),
    path("confirmation/<uuid:reference>/", views.confirmation, name="enrollment_confirmation"),
    path("confirmation/group/<uuid:family_group>/", views.confirmation_group, name="enrollment_confirmation_group"),
    path("print/<uuid:reference>/", views.print_application, name="enrollment_print"),
    path("add-child/", views.apply_add_child, name="enrollment_apply_add_child"),
    path("edit/<uuid:reference>/", views.apply_edit_start, name="enrollment_apply_edit"),
    path("", views.apply_start, name="apply"),
    path("<slug:step>/", views.apply_wizard, name="enrollment_apply"),
]
