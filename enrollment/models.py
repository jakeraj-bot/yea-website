import uuid

from django.db import models


class EnrollmentApplication(models.Model):
    GENDER_CHOICES = [("female", "Female"), ("male", "Male")]
    LANGUAGE_CHOICES = [("english", "English"), ("spanish", "Spanish"), ("other", "Other")]
    RELATIONSHIP_CHOICES = [
        ("mother", "Mother"),
        ("father", "Father"),
        ("guardian", "Guardian"),
        ("other", "Other"),
    ]
    PHONE_TYPE_CHOICES = [("cell", "Cell Phone"), ("home", "Home Phone")]
    YES_NO = [("yes", "Yes"), ("no", "No")]
    LOCATION_CHOICES = [
        ("school_18", "School 18 — Paterson"),
        ("school_26", "School 26 — Paterson"),
        ("dale_ave", "Dale Ave — Paterson (bus to School 18)"),
        ("caldwell", "Caldwell University"),
    ]
    PROGRAM_CHOICES = [
        ("after_school", "After-school program"),
        ("summer_camp", "Summer camp"),
    ]
    ETHNICITY_CHOICES = [
        ("hispanic", "Hispanic/Latino"),
        ("non_hispanic", "Non-Hispanic/Latino"),
        ("unknown", "Unknown"),
    ]
    RACE_CHOICES = [
        ("black", "Black or African American"),
        ("white", "White"),
        ("native_hawaiian", "Native Hawaiian"),
        ("asian", "Asian"),
        ("american_indian", "American Indian"),
        ("unknown", "Unknown"),
        ("other", "Other"),
    ]
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
    HEALTH_STATEMENT_CHOICES = [
        ("good_health", "My child is in good health and can participate in normal activities."),
        (
            "needs_accommodation",
            "My child can participate but has conditions requiring special accommodation.",
        ),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("private_pay", "Private Pay (card)"),
        ("4cs", "4Cs"),
        ("other", "Other"),
    ]
    PAYMENT_PLAN_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Bi-Weekly"),
        ("monthly", "Monthly"),
    ]

    reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    family_group = models.UUIDField(null=True, blank=True, db_index=True)
    child_number = models.PositiveSmallIntegerField(default=1)
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Program
    program = models.CharField(
        max_length=20, choices=PROGRAM_CHOICES, default="after_school"
    )
    program_location = models.CharField(max_length=20, choices=LOCATION_CHOICES)
    needs_dale_ave_bus = models.BooleanField(default=False)

    # Family
    family_name = models.CharField(max_length=120)
    primary_email = models.EmailField()
    home_address = models.TextField()

    # Primary parent
    primary_first_name = models.CharField(max_length=80)
    primary_last_name = models.CharField(max_length=80)
    primary_gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    primary_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    primary_language_other = models.CharField(max_length=80, blank=True)
    primary_relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    primary_relationship_other = models.CharField(max_length=80, blank=True)
    primary_phone = models.CharField(max_length=30)
    primary_phone_type = models.CharField(max_length=10, choices=PHONE_TYPE_CHOICES)
    primary_text_subscription = models.CharField(max_length=3, choices=YES_NO)
    primary_email_subscription = models.CharField(max_length=3, choices=YES_NO)
    primary_email_address = models.EmailField()
    primary_authorized_pickup = models.CharField(max_length=3, choices=YES_NO)

    # Secondary parent (optional)
    secondary_first_name = models.CharField(max_length=80, blank=True)
    secondary_last_name = models.CharField(max_length=80, blank=True)
    secondary_gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    secondary_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, blank=True)
    secondary_language_other = models.CharField(max_length=80, blank=True)
    secondary_relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, blank=True)
    secondary_relationship_other = models.CharField(max_length=80, blank=True)
    secondary_phone = models.CharField(max_length=30, blank=True)
    secondary_phone_type = models.CharField(max_length=10, choices=PHONE_TYPE_CHOICES, blank=True)
    secondary_text_subscription = models.CharField(max_length=3, choices=YES_NO, blank=True)
    secondary_email_subscription = models.CharField(max_length=3, choices=YES_NO, blank=True)
    secondary_email_address = models.EmailField(blank=True)
    secondary_authorized_pickup = models.CharField(max_length=3, choices=YES_NO, blank=True)

    # Student
    student_first_name = models.CharField(max_length=80)
    student_last_name = models.CharField(max_length=80)
    student_gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    student_dob = models.DateField()
    student_language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    student_language_other = models.CharField(max_length=80, blank=True)
    student_ethnicity = models.CharField(max_length=20, choices=ETHNICITY_CHOICES)
    student_race = models.CharField(max_length=30, choices=RACE_CHOICES)
    student_race_other = models.CharField(max_length=80, blank=True)
    student_grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    student_school = models.CharField(max_length=120)

    # Medical
    doctor_name = models.CharField(max_length=120, blank=True)
    doctor_phone = models.CharField(max_length=30, blank=True)
    insurance_provider = models.CharField(max_length=120, blank=True)
    insurance_policy_group = models.CharField(max_length=120, blank=True)
    insurance_member_id = models.CharField(max_length=120, blank=True)
    no_insurance = models.BooleanField(default=False)
    allergies = models.TextField(blank=True)
    no_known_allergies = models.BooleanField(default=False)
    requires_allergy_plan = models.BooleanField(default=False)
    requires_asthma_plan = models.BooleanField(default=False)
    requires_epipen_plan = models.BooleanField(default=False)
    has_disability = models.CharField(max_length=3, choices=YES_NO, blank=True)
    has_special_needs = models.CharField(max_length=3, choices=YES_NO, blank=True)
    requires_medication = models.CharField(max_length=3, choices=YES_NO, blank=True)
    has_medical_condition = models.CharField(max_length=3, choices=YES_NO, blank=True)
    medical_condition_explain = models.TextField(blank=True)
    health_statement = models.CharField(max_length=30, choices=HEALTH_STATEMENT_CHOICES)

    # Billing
    membership_fee_agreed = models.CharField(max_length=3, choices=YES_NO)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_method_other = models.CharField(max_length=120, blank=True)
    late_fees_understood = models.BooleanField(default=False)
    payment_plan = models.CharField(max_length=20, choices=PAYMENT_PLAN_CHOICES)
    payment_plan_signature = models.CharField(max_length=120)
    payment_plan_signed_date = models.DateField()
    four_cs_signature = models.CharField(max_length=120, blank=True)
    four_cs_signed_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student_first_name} {self.student_last_name} ({self.reference})"


class EmergencyContact(models.Model):
    application = models.ForeignKey(
        EnrollmentApplication, on_delete=models.CASCADE, related_name="emergency_contacts"
    )
    order = models.PositiveSmallIntegerField()
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30)
    relationship = models.CharField(max_length=80)
    authorized_pickup = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]


class PolicySignature(models.Model):
    application = models.ForeignKey(
        EnrollmentApplication, on_delete=models.CASCADE, related_name="policy_signatures"
    )
    policy_slug = models.CharField(max_length=80)
    policy_title = models.CharField(max_length=200)
    signature_name = models.CharField(max_length=120)
    signed_date = models.DateField()
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("application", "policy_slug")]
