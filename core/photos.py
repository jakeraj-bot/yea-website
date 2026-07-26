"""Photo paths for site templates (relative to static/).

School 18 photos come from program activity folders (not dale ave/).
Featured image is excluded from the page gallery list.
"""

HOME_GALLERY = [f"images/site/gallery/{i:02d}.jpg" for i in range(1, 13)]

SCHOOL_18_FEATURED = "images/site/locations/school-18.jpg"

SCHOOL_18_GALLERY = [f"images/site/school-18/{i:02d}.jpg" for i in range(1, 11)]

# School 26 photos not yet available.
SCHOOL_26_GALLERY = []

DALE_AVE_FEATURED = "images/site/dale-ave/01.jpg"
DALE_AVE_GALLERY = [f"images/site/dale-ave/{i:02d}.jpg" for i in range(1, 14)]

# Skip caldwell/01 — used as the summer camp program card image site-wide.
CALDWELL_GALLERY = [f"images/site/caldwell/{i:02d}.jpg" for i in range(2, 11)]

DONATE_GALLERY = [f"images/site/donate/{i:02d}.jpg" for i in range(1, 5)]

PROGRAM_AFTER_SCHOOL_GALLERY = [
    f"images/site/programs/after-school-gallery/{i:02d}.jpg" for i in range(1, 7)
]

PROGRAM_SUMMER_GALLERY = [
    f"images/site/programs/summer-gallery/{i:02d}.jpg" for i in range(1, 7)
]
