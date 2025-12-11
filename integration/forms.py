from django import forms
from .models import *


class WebRequestForm(forms.ModelForm):
    class Meta:
        model = WebRequest
        fields = ["nickname", "method", "url", "headers", "body", "active"]
