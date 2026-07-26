from django.shortcuts import render

from .partners import PARTNERS


def index(request):
    return render(request, "partnerships/index.html", {"partners": PARTNERS})
