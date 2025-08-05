from django import forms
from crispy_forms.helper import FormHelper
from .models import *

class PhotoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = Photo
        exclude = ["last_updated"]
