from django.db import models


class PortalUnit(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    program_type = models.CharField(max_length=32, blank=True, default="after_school")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    manager_name = models.CharField(max_length=120, blank=True)
    capacity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalProgram(models.Model):
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="programs")
    name = models.CharField(max_length=120)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    program_type = models.CharField(max_length=32, blank=True, default="after_school")
    season = models.CharField(max_length=64, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reg_open = models.DateField(null=True, blank=True)
    reg_close = models.DateField(null=True, blank=True)
    age_min = models.CharField(max_length=16, blank=True)
    age_max = models.CharField(max_length=16, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    status_label = models.CharField(max_length=64, blank=True, default="Active")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} · {self.unit.name}"


class PortalFamily(models.Model):
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="families")
    slug = models.SlugField()
    name = models.CharField(max_length=120)
    primary_contact = models.CharField(max_length=120, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_type = models.CharField(max_length=64, blank=True)
    program_label = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=64, default="Active")

    class Meta:
        ordering = ["name"]
        unique_together = [("unit", "slug")]

    def __str__(self):
        return self.name


class PortalChild(models.Model):
    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="children")
    name = models.CharField(max_length=120)
    grade = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)
    billing_plan = models.CharField(max_length=64, default="Weekly")
    billing_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    auto_charge = models.BooleanField(default=False)
    next_charge_date = models.DateField(null=True, blank=True)
    last_auto_charge_date = models.DateField(null=True, blank=True)
    charge_weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    charge_month_day = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AttendanceRecord(models.Model):
    STATUS_EXPECTED = "expected"
    STATUS_PRESENT = "present"
    STATUS_ABSENT = "absent"
    STATUS_CHOICES = [
        (STATUS_EXPECTED, "Expected"),
        (STATUS_PRESENT, "Present"),
        (STATUS_ABSENT, "Absent"),
    ]

    child = models.ForeignKey(PortalChild, on_delete=models.CASCADE, related_name="attendance_records")
    program = models.ForeignKey(PortalProgram, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_EXPECTED)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    method = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["child__name"]
        unique_together = [("child", "program", "date")]

    def __str__(self):
        return f"{self.child.name} · {self.date} · {self.status}"


class PortalIncident(models.Model):
    legacy_id = models.CharField(max_length=64, blank=True, unique=True, null=True)
    child = models.ForeignKey(PortalChild, on_delete=models.CASCADE, related_name="incidents")
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="incidents")
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    incident_type = models.CharField(max_length=64)
    severity = models.CharField(max_length=32)
    summary = models.CharField(max_length=255)
    location = models.CharField(max_length=120, blank=True)
    staff_reported = models.CharField(max_length=120, blank=True, default="Staff")
    parent_notified = models.BooleanField(default=False)
    parent_notified_time = models.TimeField(null=True, blank=True)
    details = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"{self.child.name} · {self.incident_type}"


class SupportTicket(models.Model):
    ticket_id = models.CharField(max_length=32, unique=True)
    from_area = models.CharField(max_length=16)
    family = models.ForeignKey(PortalFamily, null=True, blank=True, on_delete=models.SET_NULL)
    from_name = models.CharField(max_length=120)
    from_detail = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=32, default="other")
    status = models.CharField(max_length=32, default="Open")
    preview_family_slug = models.CharField(max_length=64, blank=True)
    unread_for_admin = models.PositiveIntegerField(default=0)
    unread_for_user = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject


class SupportMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.CharField(max_length=120)
    role = models.CharField(max_length=64)
    body = models.TextField()
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


class SupportAttachment(models.Model):
    message = models.ForeignKey(SupportMessage, on_delete=models.CASCADE, related_name="attachments")
    file = models.ImageField(upload_to="portal/support/%Y/%m/")
    label = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.label or self.file.name


class MessageThread(models.Model):
    legacy_id = models.SlugField(unique=True)
    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=32, default="general")
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="message_threads")
    priority = models.CharField(max_length=16, default="normal")
    unread_for_staff = models.PositiveIntegerField(default=0)
    unread_for_admin = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class TeamMessage(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    author = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    body = models.TextField()
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


class PortalAnnouncement(models.Model):
    legacy_id = models.CharField(max_length=64, blank=True, unique=True, null=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="announcements")
    audience = models.CharField(max_length=255, blank=True)
    channels = models.JSONField(default=list)
    status = models.CharField(max_length=32, default="Draft")
    style = models.CharField(max_length=32, default="info")
    posted_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-posted_date", "title"]


class PortalNewsletter(models.Model):
    legacy_id = models.CharField(max_length=64, blank=True, unique=True, null=True)
    title = models.CharField(max_length=255)
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="newsletters")
    template_id = models.CharField(max_length=64, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    sections = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=32, default="Draft")
    sent_date = models.DateField(null=True, blank=True)
    recipients_label = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-sent_date", "title"]


class PortalStaffRole(models.Model):
    name = models.CharField(max_length=64, unique=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalBillingDefaultRule(models.Model):
    role_name = models.CharField(max_length=64, unique=True)
    can_add_charge = models.BooleanField(default=True)
    can_delete_charge = models.BooleanField(default=False)
    can_add_credit = models.BooleanField(default=False)
    can_edit_family_plans = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)

    class Meta:
        ordering = ["role_name"]

    def __str__(self):
        return self.role_name


class PortalStaffAccount(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="portal_staff_account",
    )
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="staff_accounts")
    display_name = models.CharField(max_length=120)
    role = models.CharField(max_length=64, default="Unit staff")
    all_units_access = models.BooleanField(default=False)
    accessible_units = models.ManyToManyField(PortalUnit, blank=True, related_name="staff_with_access")
    can_add_charge = models.BooleanField(default=True)
    can_delete_charge = models.BooleanField(default=False)
    can_add_credit = models.BooleanField(default=False)
    can_edit_family_plans = models.BooleanField(default=False)
    charge_type_permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.display_name} · {self.unit.name}"

    @property
    def login_username(self):
        from .usernames import display_username

        return display_username(self.user.username)


class PortalParentAccount(models.Model):
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="portal_parent_account",
    )
    family = models.OneToOneField(
        PortalFamily,
        on_delete=models.CASCADE,
        related_name="parent_account",
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    autopay_enabled = models.BooleanField(default=False)
    autopay_day = models.CharField(max_length=64, blank=True)
    email_receipts = models.BooleanField(default=True)
    email_reminders = models.BooleanField(default=True)
    sms_reminders = models.BooleanField(default=False)
    profile_photo = models.ImageField(upload_to="portal/parent-photos/%Y/%m/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["family__name"]

    def __str__(self):
        return f"{self.login_username} · {self.family.name}"

    @property
    def login_username(self):
        from .usernames import display_username

        return display_username(self.user.username)


class PortalLedgerEntry(models.Model):
    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="ledger_entries")
    child_name = models.CharField(max_length=120, blank=True)
    date = models.DateField()
    entry_type = models.CharField(max_length=32)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.family.name} · {self.description}"


class PortalPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_FAILED, "Failed"),
    ]

    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="payments")
    receipt_no = models.CharField(max_length=32, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_charged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    method_label = models.CharField(max_length=120, blank=True)
    payment_kind = models.CharField(max_length=32, default="balance")
    dropin_child = models.CharField(max_length=120, blank=True)
    dropin_program = models.CharField(max_length=120, blank=True)
    dropin_location = models.CharField(max_length=120, blank=True)
    dropin_date = models.CharField(max_length=64, blank=True)
    dropin_booking = models.ForeignKey(
        "dropin.DropInBooking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_payments",
    )
    stripe_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.receipt_no or f"Payment {self.pk}"


class PortalAgencyProfile(models.Model):
    """4Cs agency enrollment for one child — separate from regular family billing."""

    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="agency_profiles")
    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="agency_profiles")
    child = models.OneToOneField(PortalChild, on_delete=models.CASCADE, related_name="agency_profile")
    agency = models.ForeignKey(
        "PortalAgency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_profiles",
    )
    auth_number = models.CharField(max_length=64)
    auth_start = models.DateField(null=True, blank=True)
    auth_end = models.DateField(null=True, blank=True)
    weekly_copay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weekly_agency_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    use_variable_rates = models.BooleanField(default=False)
    rate_tier_key = models.CharField(max_length=64, blank=True)
    daily_copay_rates = models.JSONField(default=dict, blank=True)
    agency_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["child__name"]

    def __str__(self):
        return f"{self.child.name} · {self.auth_number}"


class PortalAgencyLedgerEntry(models.Model):
    profile = models.ForeignKey(PortalAgencyProfile, on_delete=models.CASCADE, related_name="ledger_entries")
    date = models.DateField()
    entry_type = models.CharField(max_length=32)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]


class PortalAgencyRemittance(models.Model):
    unit = models.ForeignKey(PortalUnit, on_delete=models.CASCADE, related_name="agency_remittances")
    date = models.DateField()
    reference = models.CharField(max_length=64)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]


class PortalAgencyRemittanceAllocation(models.Model):
    remittance = models.ForeignKey(PortalAgencyRemittance, on_delete=models.CASCADE, related_name="allocations")
    profile = models.ForeignKey(PortalAgencyProfile, on_delete=models.CASCADE, related_name="remittance_allocations")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["profile__child__name"]


class PortalProfileChangeRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    account = models.ForeignKey(
        PortalParentAccount,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    changes = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.account.family.name} · {self.status}"


class PortalAgency(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    default_weekly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remittance_schedule = models.CharField(max_length=64, blank=True, default="Monthly (1st business day)")
    rate_tiers = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    units = models.ManyToManyField(PortalUnit, blank=True, related_name="agencies")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Portal agencies"

    def __str__(self):
        return self.name


class PortalFeeRule(models.Model):
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    amount = models.CharField(max_length=32, blank=True)
    display = models.CharField(max_length=64, blank=True)
    frequency = models.CharField(max_length=64, blank=True)
    period = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalPaymentPlan(models.Model):
    name = models.CharField(max_length=64)
    interval = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalProcessingFee(models.Model):
    name = models.CharField(max_length=64)
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    flat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalTaxStatementSetting(models.Model):
    require_zero_balance = models.BooleanField(default=True)
    parents_enabled = models.BooleanField(default=True)
    staff_can_view = models.JSONField(default=list, blank=True)

    def __str__(self):
        return "Tax statement settings"


class PortalScholarshipFund(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalScholarshipAssignment(models.Model):
    child = models.ForeignKey(PortalChild, on_delete=models.CASCADE, related_name="scholarships")
    fund = models.ForeignKey(PortalScholarshipFund, on_delete=models.CASCADE, related_name="assignments")
    full_rate = models.DecimalField(max_digits=10, decimal_places=2)
    parent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="Active")

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.child.name} · {self.fund.name}"


class PortalOrgPolicy(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    version = models.CharField(max_length=32, blank=True, default="1.0")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "Portal org policies"

    def __str__(self):
        return self.title


class PortalPolicySignatureRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SIGNED = "signed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SIGNED, "Signed"),
    ]

    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="policy_requests")
    child = models.ForeignKey(PortalChild, on_delete=models.CASCADE, related_name="policy_requests")
    policy = models.ForeignKey(PortalOrgPolicy, on_delete=models.CASCADE, related_name="signature_requests")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notified_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-notified_at"]
        unique_together = [("child", "policy")]

    def __str__(self):
        return f"{self.child.name} · {self.policy.title}"


class PortalCheckInSetting(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return self.label


class PortalWaivedAbsenceCharge(models.Model):
    family_slug = models.SlugField()
    child_name = models.CharField(max_length=120)
    week_label = models.CharField(max_length=64)
    charge_description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    waived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-waived_at"]
        unique_together = [("family_slug", "child_name", "week_label", "charge_description")]


class PortalFieldTrip(models.Model):
    unit = models.ForeignKey(
        PortalUnit,
        on_delete=models.CASCADE,
        related_name="field_trips",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    trip_date = models.DateField()
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    permission_slip = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trip_date", "-created_at"]

    def __str__(self):
        return self.title


class PortalFieldTripSignup(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SIGNED = "signed"
    STATUS_PAID = "paid"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Needs signature"),
        (STATUS_SIGNED, "Signed — pay now"),
        (STATUS_PAID, "Paid"),
    ]

    trip = models.ForeignKey(PortalFieldTrip, on_delete=models.CASCADE, related_name="signups")
    child = models.ForeignKey(PortalChild, on_delete=models.CASCADE, related_name="field_trip_signups")
    family = models.ForeignKey(PortalFamily, on_delete=models.CASCADE, related_name="field_trip_signups")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    signature_name = models.CharField(max_length=120, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    payment = models.ForeignKey(
        PortalPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_trip_signups",
    )

    class Meta:
        ordering = ["child__name"]
        unique_together = [("trip", "child")]

    def __str__(self):
        return f"{self.child.name} · {self.trip.title}"

