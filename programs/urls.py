from django.urls import path

from . import views

urlpatterns = [
    path("after-school/", views.after_school, name="after_school"),
    path("summer-camp/", views.summer_camp, name="summer_camp"),
    path("locations/school-18/", views.school_18, name="school_18"),
    path("locations/school-26/", views.school_26, name="school_26"),
    path("locations/dale-ave/", views.dale_ave, name="dale_ave"),
    path("locations/caldwell-university/", views.caldwell, name="caldwell"),
]
