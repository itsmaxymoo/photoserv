from django import forms
from crispy_forms.helper import FormHelper
from .models import User


class UserForm(forms.ModelForm):
    new_password = forms.CharField(
        label="New password",
        widget=forms.PasswordInput,
        required=False
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput,
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        # If one is filled, ensure both are filled
        if new_password or confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        new_password = self.cleaned_data.get("new_password")

        if new_password:
            user.set_password(new_password)  # securely hash password

        if commit:
            user.save()
        return user
