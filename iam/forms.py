from django import forms
from crispy_forms.helper import FormHelper
from .models import *


class UserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
