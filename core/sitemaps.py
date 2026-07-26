from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "home",
            "after_school",
            "summer_camp",
            "school_18",
            "school_26",
            "dale_ave",
            "caldwell",
            "dropin_index",
            "apply",
            "donate",
            "partnerships",
            "our_story",
            "meet_the_staff",
            "contact",
            "safety",
        ]

    def location(self, item):
        if item == "apply":
            return reverse("apply")
        if item == "dropin_index":
            return reverse("dropin_index")
        return reverse(item)
