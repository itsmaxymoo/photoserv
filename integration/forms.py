from django import forms
from .models import *


class WebRequestForm(forms.ModelForm):
    class Meta:
        model = WebRequest
        fields = ["nickname", "method", "url", "headers", "body", "active"]


class PythonPluginForm(forms.ModelForm):

    class Meta:
        model = PythonPlugin
        fields = ["nickname", "module", "config", "active"]


class PhotoPluginExclusionForm(forms.Form):
    """
    Form for managing plugin exclusions for a photo.
    This form handles which plugins should be excluded from publish/unpublish notifications.
    """
    excluded_plugins = forms.ModelMultipleChoiceField(
        queryset=None,  # Set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Exclude from publish/unpublish notification",
        help_text="Select plugins to exclude from being notified about this photo's publish/unpublish event. This setting is per-edit."
    )

    def __init__(self, *args, photo_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.photo_instance = photo_instance

        # Dynamically populate excluded_plugins queryset
        try:
            self.fields['excluded_plugins'].queryset = PythonPlugin.objects.order_by('nickname', 'module')
            
            # Pre-populate with existing exclusions if editing
            if self.photo_instance and self.photo_instance.pk:
                excluded_ids = PhotoPluginExclusion.objects.filter(
                    photo=self.photo_instance
                ).values_list('plugin_id', flat=True)
                self.fields['excluded_plugins'].initial = excluded_ids
        except Exception:
            # If integration app is not available, use empty queryset
            from django.db.models import Model
            self.fields['excluded_plugins'].queryset = Model.objects.none()

    def setup_exclusions(self, photo):
        """
        Set up plugin exclusions for a photo based on form data.
        Must be called after the photo has been saved and has an ID.
        """
        # Clear any existing exclusions for this photo
        PhotoPluginExclusion.objects.filter(photo=photo).delete()
        
        # Create new exclusions based on form selection
        excluded_plugins = self.cleaned_data.get('excluded_plugins', [])
        for plugin in excluded_plugins:
            PhotoPluginExclusion.objects.create(photo=photo, plugin=plugin)
