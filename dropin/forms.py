from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import formset_factory

from enrollment.policies_data import POLICIES

from . import constants
from .models import DropInChild, DropInFamilyProfile


class AccountStepForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email address")
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")


class FamilyStepForm(forms.Form):
    family_name = forms.CharField(max_length=120, label="Family name")
    primary_email = forms.EmailField(label="Primary email")
    home_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Home address")
    primary_first_name = forms.CharField(max_length=80, label="Primary parent/guardian first name")
    primary_last_name = forms.CharField(max_length=80, label="Primary parent/guardian last name")
    primary_phone = forms.CharField(max_length=30, label="Primary phone")
    secondary_first_name = forms.CharField(max_length=80, required=False, label="Secondary parent first name")
    secondary_last_name = forms.CharField(max_length=80, required=False, label="Secondary parent last name")
    secondary_phone = forms.CharField(max_length=30, required=False, label="Secondary phone")


class ChildStepForm(forms.Form):
    first_name = forms.CharField(max_length=80, label="Child first name")
    last_name = forms.CharField(max_length=80, label="Child last name")
    gender = forms.ChoiceField(choices=DropInChild.GENDER_CHOICES, label="Gender")
    date_of_birth = forms.DateField(label="Date of birth", widget=forms.DateInput(attrs={"type": "date"}))
    grade = forms.ChoiceField(choices=DropInChild.GRADE_CHOICES, label="Grade")
    school = forms.CharField(max_length=120, label="School")


class EmergencyContactForm(forms.Form):
    first_name = forms.CharField(max_length=80, label="First name")
    last_name = forms.CharField(max_length=80, label="Last name")
    phone = forms.CharField(max_length=30, label="Phone")
    relationship = forms.CharField(max_length=80, label="Relationship to child")
    authorized_pickup = forms.BooleanField(required=False, label="Authorized to pick up")


EmergencyContactFormSet = formset_factory(EmergencyContactForm, extra=2, min_num=2, max_num=2, validate_min=True)


class MedicalStepForm(forms.Form):
    YES_NO = [("yes", "Yes"), ("no", "No")]
    HEALTH_STATEMENT_CHOICES = [
        ("good_health", "My child is in good health and can participate in normal activities."),
        (
            "needs_accommodation",
            "My child can participate but has conditions requiring special accommodation.",
        ),
    ]

    doctor_name = forms.CharField(max_length=120, required=False, label="Doctor's name")
    doctor_phone = forms.CharField(max_length=30, required=False, label="Doctor's phone")
    allergies = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Allergies")
    no_known_allergies = forms.BooleanField(required=False, label="No known allergies")
    requires_allergy_plan = forms.BooleanField(required=False, label="Allergy Action Plan required")
    requires_asthma_plan = forms.BooleanField(required=False, label="Asthma Action Plan required")
    requires_epipen_plan = forms.BooleanField(required=False, label="EpiPen Plan required")
    has_medical_condition = forms.ChoiceField(
        choices=[("", "---------")] + YES_NO,
        required=False,
        label="Medical condition?",
    )
    medical_condition_explain = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Please explain any medical conditions",
    )
    health_statement = forms.ChoiceField(
        choices=HEALTH_STATEMENT_CHOICES,
        widget=forms.RadioSelect,
        label="Health statement",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("no_known_allergies"):
            cleaned["allergies"] = ""
            cleaned["requires_allergy_plan"] = False
        return cleaned


def build_policy_step_form():
    fields = {}
    for policy in POLICIES:
        slug = policy["slug"]
        fields[f"{slug}__signature"] = forms.CharField(
            max_length=120,
            label=f"Signature — {policy['title']}",
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
    return type("DropInPolicyStepForm", (forms.Form,), fields)


PolicyStepForm = build_policy_step_form()


class BookingForm(forms.Form):
    program = forms.ChoiceField(choices=constants.PROGRAM_CHOICES, label="Program")
    location = forms.ChoiceField(choices=constants.LOCATION_CHOICES, label="Location")
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}))
    child = forms.ModelChoiceField(queryset=DropInChild.objects.none(), label="Child")

    def __init__(self, profile, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["child"].queryset = profile.children.all()

    def clean(self):
        cleaned = super().clean()
        program = cleaned.get("program")
        location = cleaned.get("location")
        if program == constants.PROGRAM_AFTER_SCHOOL and location not in constants.AFTER_SCHOOL_LOCATIONS:
            self.add_error("location", "Choose an after-school location.")
        if program == constants.PROGRAM_SUMMER_CAMP and location not in constants.SUMMER_CAMP_LOCATIONS:
            self.add_error("location", "Summer camp drop-in is at Caldwell University only.")
        return cleaned


STEP_FORMS = {
    "account": AccountStepForm,
    "family": FamilyStepForm,
    "child": ChildStepForm,
    "medical": MedicalStepForm,
    "policies": PolicyStepForm,
}

STEP_TITLES = {
    "account": "Create your account",
    "family": "Family information",
    "child": "Child information",
    "emergency": "Emergency contacts",
    "medical": "Medical information",
    "policies": "Policies & signatures (one time)",
    "review": "Review & submit",
}

STEP_ORDER = ["account", "family", "child", "emergency", "medical", "policies", "review"]
