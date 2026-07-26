from django.shortcuts import render

from core import photos


def after_school(request):
    return render(
        request,
        "programs/after_school.html",
        {
            "gallery_photos": photos.PROGRAM_AFTER_SCHOOL_GALLERY,
            "school_18_photo": photos.SCHOOL_18_FEATURED,
            "dale_ave_photo": photos.DALE_AVE_FEATURED,
        },
    )


def summer_camp(request):
    return render(
        request,
        "programs/summer_camp.html",
        {"gallery_photos": photos.PROGRAM_SUMMER_GALLERY},
    )


def school_18(request):
    return render(
        request,
        "programs/school_18.html",
        {
            "featured_photo": photos.SCHOOL_18_FEATURED,
            "gallery_photos": photos.SCHOOL_18_GALLERY,
        },
    )


def school_26(request):
    return render(request, "programs/school_26.html")


def dale_ave(request):
    return render(
        request,
        "programs/dale_ave.html",
        {
            "featured_photo": photos.DALE_AVE_FEATURED,
            "gallery_photos": photos.DALE_AVE_GALLERY,
        },
    )


def caldwell(request):
    return render(
        request,
        "programs/caldwell.html",
        {"gallery_photos": photos.CALDWELL_GALLERY},
    )
