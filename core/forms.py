from django import forms


class ContactForm(forms.Form):
    TOPIC_CHOICES = [
        ("after_school", "After-school program"),
        ("summer_camp", "Summer camp"),
        ("partnership", "Partnership"),
        ("donation", "Donation"),
        ("general", "General"),
    ]

    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    topic = forms.ChoiceField(choices=TOPIC_CHOICES)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}))
    company = forms.CharField(
        required=False,
        label="Company",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "aria-hidden": "true",
            }
        ),
    )
