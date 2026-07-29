from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


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
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken — try another or log in.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists — try logging in.")
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
