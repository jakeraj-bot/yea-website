from django import forms
from django.forms import formset_factory

from .models import EnrollmentApplication
from .policies_data import POLICIES


class ProgramStepForm(forms.Form):
    program = forms.ChoiceField(
        choices=EnrollmentApplication.PROGRAM_CHOICES,
        widget=forms.RadioSelect,
        label="Which program are you applying for?",
    )
    program_location = forms.ChoiceField(
        choices=EnrollmentApplication.LOCATION_CHOICES,
        label="Which location?",
    )

    def clean(self):
        cleaned = super().clean()
        program = cleaned.get("program")
        location = cleaned.get("program_location")
        after_school_locations = {"school_18", "school_26", "dale_ave"}
        if program == "after_school" and location == "caldwell":
            self.add_error(
                "program_location",
                "Caldwell University is for summer camp only. Choose an after-school location.",
            )
        if program == "summer_camp" and location in after_school_locations:
            self.add_error(
                "program_location",
                "School 18, School 26, and Dale Ave are after-school locations only.",
            )
        return cleaned


class FamilyStepForm(forms.Form):
    family_name = forms.CharField(max_length=120, label="Family name")
    primary_email = forms.EmailField(label="Primary email")
    home_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Home address")

    primary_first_name = forms.CharField(max_length=80, label="First name")
    primary_last_name = forms.CharField(max_length=80, label="Last name")
    primary_gender = forms.ChoiceField(choices=EnrollmentApplication.GENDER_CHOICES, label="Gender")
    primary_language = forms.ChoiceField(choices=EnrollmentApplication.LANGUAGE_CHOICES, label="Primary language")
    primary_language_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    primary_relationship = forms.ChoiceField(
        choices=EnrollmentApplication.RELATIONSHIP_CHOICES, label="Relationship to child"
    )
    primary_relationship_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    primary_phone = forms.CharField(max_length=30, label="Phone #")
    primary_phone_type = forms.ChoiceField(
        choices=EnrollmentApplication.PHONE_TYPE_CHOICES, label="Phone type"
    )
    primary_text_subscription = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Text message subscription"
    )
    primary_email_subscription = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Email subscription"
    )
    primary_email_address = forms.EmailField(label="Email address")
    primary_authorized_pickup = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Authorized to pick up?"
    )

    secondary_first_name = forms.CharField(max_length=80, required=False, label="First name")
    secondary_last_name = forms.CharField(max_length=80, required=False, label="Last name")
    secondary_gender = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.GENDER_CHOICES,
        required=False,
        label="Gender",
    )
    secondary_language = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.LANGUAGE_CHOICES,
        required=False,
        label="Primary language",
    )
    secondary_language_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    secondary_relationship = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.RELATIONSHIP_CHOICES,
        required=False,
        label="Relationship to child",
    )
    secondary_relationship_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    secondary_phone = forms.CharField(max_length=30, required=False, label="Phone #")
    secondary_phone_type = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.PHONE_TYPE_CHOICES,
        required=False,
        label="Phone type",
    )
    secondary_text_subscription = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.YES_NO,
        required=False,
        label="Text message subscription",
    )
    secondary_email_subscription = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.YES_NO,
        required=False,
        label="Email subscription",
    )
    secondary_email_address = forms.EmailField(required=False, label="Email address")
    secondary_authorized_pickup = forms.ChoiceField(
        choices=[("", "---------")] + EnrollmentApplication.YES_NO,
        required=False,
        label="Authorized to pick up?",
    )


class StudentStepForm(forms.Form):
    student_first_name = forms.CharField(max_length=80, label="Student first name")
    student_last_name = forms.CharField(max_length=80, label="Student last name")
    student_gender = forms.ChoiceField(choices=EnrollmentApplication.GENDER_CHOICES, label="Gender")
    student_dob = forms.DateField(label="Date of birth", widget=forms.DateInput(attrs={"type": "date"}))
    student_language = forms.ChoiceField(
        choices=EnrollmentApplication.LANGUAGE_CHOICES, label="Primary language"
    )
    student_language_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    student_ethnicity = forms.ChoiceField(
        choices=EnrollmentApplication.ETHNICITY_CHOICES, label="Ethnicity"
    )
    student_race = forms.ChoiceField(choices=EnrollmentApplication.RACE_CHOICES, label="Race")
    student_race_other = forms.CharField(max_length=80, required=False, label="If other, specify")
    student_grade = forms.ChoiceField(choices=EnrollmentApplication.GRADE_CHOICES, label="Grade")
    student_school = forms.CharField(max_length=120, label="School")

    doctor_name = forms.CharField(max_length=120, label="Doctor's name")
    doctor_phone = forms.CharField(max_length=30, label="Doctor's phone #")
    insurance_provider = forms.CharField(max_length=120, required=False, label="Insurance provider")
    insurance_policy_group = forms.CharField(max_length=120, required=False, label="Policy/Group #")
    insurance_member_id = forms.CharField(max_length=120, required=False, label="Member ID #")
    no_insurance = forms.BooleanField(required=False, label="No insurance")
    allergies = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Allergies")
    no_known_allergies = forms.BooleanField(required=False, label="No known allergies")
    requires_allergy_plan = forms.BooleanField(required=False, label="Child requires an Allergy Action Plan")
    requires_asthma_plan = forms.BooleanField(required=False, label="Child requires an Asthma Action Plan")
    requires_epipen_plan = forms.BooleanField(required=False, label="Child requires an EpiPen Plan")
    has_disability = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Disability?"
    )
    has_special_needs = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Special needs?"
    )
    requires_medication = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO, label="Medication?"
    )
    has_medical_condition = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO,
        label="Medical condition?",
    )
    medical_condition_explain = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Please explain"
    )
    health_statement = forms.ChoiceField(
        choices=EnrollmentApplication.HEALTH_STATEMENT_CHOICES,
        widget=forms.RadioSelect,
        label="Health statement (check one only)",
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("doctor_name"):
            self.add_error("doctor_name", "Doctor's name is required.")
        if not cleaned.get("doctor_phone"):
            self.add_error("doctor_phone", "Doctor's phone is required.")

        if cleaned.get("no_insurance"):
            pass
        else:
            for field in ("insurance_provider", "insurance_policy_group", "insurance_member_id"):
                if not cleaned.get(field):
                    self.add_error(field, "Required unless “No insurance” is checked.")

        if cleaned.get("no_known_allergies"):
            pass
        elif not cleaned.get("allergies"):
            self.add_error("allergies", "Required unless “No known allergies” is checked.")

        for field in ("has_disability", "has_special_needs", "requires_medication", "has_medical_condition"):
            if not cleaned.get(field):
                self.add_error(field, "Please select Yes or No.")

        if cleaned.get("has_medical_condition") == "yes" and not cleaned.get("medical_condition_explain"):
            self.add_error("medical_condition_explain", "Please explain the medical condition.")

        return cleaned


class EmergencyContactForm(forms.Form):
    first_name = forms.CharField(max_length=80, required=False, label="First name")
    last_name = forms.CharField(max_length=80, required=False, label="Last name")
    phone = forms.CharField(max_length=30, required=False, label="Phone #")
    relationship = forms.CharField(max_length=80, required=False, label="Relationship to child")
    authorized_pickup = forms.BooleanField(required=False, label="Authorized to pick up")


EmergencyContactFormSet = formset_factory(EmergencyContactForm, extra=3, max_num=3)


class BillingStepForm(forms.Form):
    membership_fee_agreed = forms.ChoiceField(
        choices=EnrollmentApplication.YES_NO,
        label="Do you agree to the $20 membership fee for the 2026–2027 school year?",
    )
    payment_method = forms.ChoiceField(
        choices=EnrollmentApplication.PAYMENT_METHOD_CHOICES, label="Payment method"
    )
    payment_method_other = forms.CharField(max_length=120, required=False, label="If other, specify")
    late_fees_understood = forms.BooleanField(
        required=True,
        label=(
            "I understand late fees: $15 for missed payment deadlines; $15 for every 15 minutes late for pickup "
            "(program closes at 6:00pm)."
        ),
    )
    payment_plan = forms.ChoiceField(
        choices=EnrollmentApplication.PAYMENT_PLAN_CHOICES, label="Preferred payment plan"
    )
    payment_plan_signature = forms.CharField(max_length=120, label="Payment plan signature (type full name)")
    payment_plan_signed_date = forms.DateField(
        label="Date", widget=forms.DateInput(attrs={"type": "date"})
    )
    four_cs_signature = forms.CharField(
        max_length=120, label="4Cs signature (type full name)"
    )
    four_cs_signed_date = forms.DateField(
        label="4Cs date", widget=forms.DateInput(attrs={"type": "date"})
    )


def build_policy_step_form():
    fields = {}
    for policy in POLICIES:
        slug = policy["slug"]
        fields[f"{slug}__signature"] = forms.CharField(
            max_length=120,
            label=f"Signature for {policy['title']}",
            help_text="Type your full legal name",
        )
        fields[f"{slug}__date"] = forms.DateField(
            label="Date signed",
            widget=forms.DateInput(attrs={"type": "date"}),
        )
        for extra in policy.get("fields", []):
            name = f"{slug}__{extra['name']}"
            if extra["type"] == "textarea":
                fields[name] = forms.CharField(
                    label=extra["label"],
                    required=extra.get("required", False),
                    widget=forms.Textarea(attrs={"rows": 3}),
                )
            elif extra["type"] == "choice":
                fields[name] = forms.ChoiceField(
                    label=extra["label"],
                    choices=extra["choices"],
                    required=extra.get("required", False),
                    widget=forms.RadioSelect,
                )
    return type("PolicyStepForm", (forms.Form,), fields)


PolicyStepForm = build_policy_step_form()


class AddChildStepForm(forms.Form):
    add_another = forms.ChoiceField(
        choices=[
            ("yes", "Yes — add another child"),
            ("no", "No — I'm finished adding children"),
        ],
        widget=forms.RadioSelect,
        label="Do you need to add another child to this application?",
    )


class PortalAccountForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"placeholder": "Choose a username for your portal login"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "At least 8 characters"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
    )

    def clean_username(self):
        from django.contrib.auth import get_user_model

        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken — choose another.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        return cleaned


STEP_FORMS = {
    "family": FamilyStepForm,
    "program": ProgramStepForm,
    "student": StudentStepForm,
    "billing": BillingStepForm,
    "policies": PolicyStepForm,
    "add_child": AddChildStepForm,
}

STEP_TITLES = {
    "family": "Family & parent/guardian information",
    "program": "Program & location",
    "student": "Student & medical information",
    "billing": "Billing & emergency contacts",
    "policies": "Policies & signatures",
    "add_child": "Add another child?",
    "review": "Review & submit",
}

STEP_TAB_LABELS = {
    "family": "Family",
    "program": "Program",
    "student": "Student",
    "billing": "Billing",
    "policies": "Policies",
    "add_child": "Add child",
    "review": "Review",
}

STEP_ORDER = ["family", "program", "student", "billing", "policies", "add_child", "review"]

FAMILY_FIELD_NAMES = [
    "family_name",
    "primary_email",
    "home_address",
    "primary_first_name",
    "primary_last_name",
    "primary_gender",
    "primary_language",
    "primary_language_other",
    "primary_relationship",
    "primary_relationship_other",
    "primary_phone",
    "primary_phone_type",
    "primary_text_subscription",
    "primary_email_subscription",
    "primary_email_address",
    "primary_authorized_pickup",
    "secondary_first_name",
    "secondary_last_name",
    "secondary_gender",
    "secondary_language",
    "secondary_language_other",
    "secondary_relationship",
    "secondary_relationship_other",
    "secondary_phone",
    "secondary_phone_type",
    "secondary_text_subscription",
    "secondary_email_subscription",
    "secondary_email_address",
    "secondary_authorized_pickup",
]

CHILD_STEP_SLUGS = frozenset({"program", "student", "billing", "policies"})
