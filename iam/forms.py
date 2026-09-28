from django import forms
from django.contrib.auth.models import Group, Permission
from crispy_forms.helper import FormHelper

from .permissions import group_permissions_by_app
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


class GroupForm(forms.ModelForm):
    """Edit a group and its complete set of Django permissions."""

    permission_field_prefix = "permission_"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        selected_permission_ids = set()
        if self.instance.pk:
            selected_permission_ids = set(
                self.instance.permissions.values_list("pk", flat=True)
            )

        self.permission_ids_by_field = {}
        permission_groups = []
        permissions = Permission.objects.select_related("content_type")
        for app_name, app_permissions in group_permissions_by_app(permissions):
            permission_fields = []
            for permission in app_permissions:
                field_name = self.permission_field_name(permission)
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    label=permission.name,
                    initial=permission.pk in selected_permission_ids,
                    widget=forms.CheckboxInput(attrs={"class": "toggle"}),
                )
                self.permission_ids_by_field[field_name] = permission.pk
                permission_fields.append(self[field_name])
            permission_groups.append((app_name, permission_fields))
        self.permission_groups = permission_groups

    class Meta:
        model = Group
        fields = ["name"]

    @classmethod
    def permission_field_name(cls, permission):
        return f"{cls.permission_field_prefix}{permission.pk}"

    def _save_m2m(self):
        super()._save_m2m()
        self.instance.permissions.set(
            permission_id
            for field_name, permission_id in self.permission_ids_by_field.items()
            if self.cleaned_data.get(field_name)
        )
