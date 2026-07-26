import uuid

from django.conf import settings
from django.db import models

from . import constants


class DropInFamilyProfile(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dropin_profile",
    )
    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    family_name = models.CharField(max_length=120)
    primary_email = models.EmailField()
    home_address = models.TextField()
    primary_first_name = models.CharField(max_length=80)
    primary_last_name = models.CharField(max_length=80)
    primary_phone = models.CharField(max_length=30)
    secondary_first_name = models.CharField(max_length=80, blank=True)
    secondary_last_name = models.CharField(max_length=80, blank=True)
    secondary_phone = models.CharField(max_length=30, blank=True)

    allergies = models.TextField(blank=True)
    no_known_allergies = models.BooleanField(default=False)
    requires_allergy_plan = models.BooleanField(default=False)
    requires_asthma_plan = models.BooleanField(default=False)
    requires_epipen_plan = models.BooleanField(default=False)
    has_medical_condition = models.CharField(max_length=3, blank=True)
    medical_condition_explain = models.TextField(blank=True)
    health_statement = models.CharField(max_length=30, blank=True)
    doctor_name = models.CharField(max_length=120, blank=True)
    doctor_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.family_name} ({self.user.username})"

    @property
    def is_booking_ready(self):
        return self.status == self.STATUS_APPROVED


class DropInChild(models.Model):
    GENDER_CHOICES = [("female", "Female"), ("male", "Male")]
    GRADE_CHOICES = [
        ("pre_k", "Pre-K"),
        ("kindergarten", "Kindergarten"),
        ("1", "1st"),
        ("2", "2nd"),
        ("3", "3rd"),
        ("4", "4th"),
        ("5", "5th"),
        ("6", "6th"),
        ("7", "7th"),
        ("8", "8th"),
    ]

    profile = models.ForeignKey(
        DropInFamilyProfile,
        on_delete=models.CASCADE,
        related_name="children",
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    school = models.CharField(max_length=120)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class DropInEmergencyContact(models.Model):
    profile = models.ForeignKey(
        DropInFamilyProfile,
        on_delete=models.CASCADE,
        related_name="emergency_contacts",
    )
    order = models.PositiveSmallIntegerField()
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30)
    relationship = models.CharField(max_length=80)
    authorized_pickup = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]


class DropInPolicySignature(models.Model):
    profile = models.ForeignKey(
        DropInFamilyProfile,
        on_delete=models.CASCADE,
        related_name="policy_signatures",
    )
    policy_slug = models.CharField(max_length=80)
    policy_title = models.CharField(max_length=200)
    signature_name = models.CharField(max_length=120)
    signed_date = models.DateField()
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("profile", "policy_slug")]


class DropInDayCapacity(models.Model):
    program = models.CharField(max_length=20, choices=constants.PROGRAM_CHOICES)
    location = models.CharField(max_length=20, choices=constants.LOCATION_CHOICES)
    date = models.DateField()
    max_slots = models.PositiveSmallIntegerField(
        help_text="Maximum drop-in spots available this day at this location.",
    )

    class Meta:
        ordering = ["date", "program", "location"]
        unique_together = [("program", "location", "date")]
        verbose_name_plural = "Drop-in day capacities"

    def __str__(self):
        return f"{self.date} · {self.get_program_display()} · {self.get_location_display()} ({self.max_slots})"


class DropInBooking(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending payment"),
        (STATUS_PAID, "Paid"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    profile = models.ForeignKey(
        DropInFamilyProfile,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    child = models.ForeignKey(DropInChild, on_delete=models.CASCADE, related_name="bookings")
    program = models.CharField(max_length=20, choices=constants.PROGRAM_CHOICES)
    location = models.CharField(max_length=20, choices=constants.LOCATION_CHOICES)
    date = models.DateField()
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    stripe_session_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = [("child", "program", "location", "date")]

    def __str__(self):
        return f"{self.child} · {self.date} · {self.get_status_display()}"


class DropInWaitlistEntry(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_OFFERED = "offered"
    STATUS_ACCEPTED = "accepted"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_WAITING, "Waiting"),
        (STATUS_OFFERED, "Offered spot"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    profile = models.ForeignKey(
        DropInFamilyProfile,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
    )
    child = models.ForeignKey(DropInChild, on_delete=models.CASCADE, related_name="waitlist_entries")
    program = models.CharField(max_length=20, choices=constants.PROGRAM_CHOICES)
    location = models.CharField(max_length=20, choices=constants.LOCATION_CHOICES)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "program", "location", "created_at"]
        unique_together = [("child", "program", "location", "date")]

    def __str__(self):
        return f"Waitlist · {self.child} · {self.date}"
