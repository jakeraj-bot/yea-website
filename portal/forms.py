from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.exceptions import ValidationError


class PortalAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, portal_type="parent", **kwargs):
        self.portal_type = portal_type
        super().__init__(*args, **kwargs)

    def clean_username(self):
        login_name = super().clean_username()
        from .usernames import resolve_auth_username

        return resolve_auth_username(self.portal_type, login_name)


class ParentSignupForm(forms.Form):
    family_name = forms.CharField(
        max_length=120,
        label="Family / last name",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Smith"}),
    )
    your_name = forms.CharField(
        max_length=120,
        label="Your full name",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Jamie Smith"}),
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@email.com"}))
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Choose a username"}),
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
        from .usernames import portal_username_taken

        username = self.cleaned_data["username"].strip()
        if portal_username_taken("parent", username):
            raise ValidationError(
                "That parent portal username is already registered — try logging in or use Forgot password below."
            )
        return username

    def clean_email(self):
        from .parent_auth import get_parent_account

        email = self.cleaned_data["email"].strip().lower()
        for user in get_user_model().objects.filter(email__iexact=email):
            if get_parent_account(user):
                raise ValidationError("A parent account with this email already exists — try logging in.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        if password1 and len(password1) < 8:
            raise ValidationError("Password must be at least 8 characters.")
        return cleaned


class PortalPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, portal_type="parent", **kwargs):
        self.portal_type = portal_type
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.setdefault("class", "portal-input")
        self.fields["email"].widget.attrs.setdefault("placeholder", "you@email.com")

    def get_users(self, email):
        active_users = get_user_model().objects.filter(email__iexact=email, is_active=True)
        for user in active_users:
            if self._user_matches_portal(user):
                yield user

    def _user_matches_portal(self, user):
        from .parent_auth import get_parent_account
        from .staff_auth import get_staff_account, is_portal_admin

        if self.portal_type == "parent":
            return bool(get_parent_account(user))
        if self.portal_type == "staff":
            return bool(get_staff_account(user))
        if self.portal_type == "admin":
            return is_portal_admin(user)
        return False
