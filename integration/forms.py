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


class IntegrationPhotoForm(forms.Form):
    """
    Form for managing plugin exclusions and entity parameters for a photo.
    This form handles which plugins should be excluded from publish/unpublish notifications
    and per-entity parameters for each plugin.
    """
    excluded_plugins = forms.ModelMultipleChoiceField(
        queryset=None,  # Set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Exclude from publish/unpublish notification",
        help_text="Select plugins to permanently exclude from being notified about this photo's publish/unpublish events."
    )

    def __init__(self, *args, photo_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.photo_instance = photo_instance

        # Dynamically populate excluded_plugins queryset
        try:
            all_plugins = PythonPlugin.objects.order_by('nickname', 'module')
            self.fields['excluded_plugins'].queryset = all_plugins
            
            # Filter for valid plugins in Python (valid is a property, not a DB field)
            valid_plugins = [plugin for plugin in all_plugins if plugin.valid]
            
            # Pre-populate with existing exclusions if editing
            if self.photo_instance and self.photo_instance.pk:
                excluded_ids = PhotoPluginExclusion.objects.filter(
                    photo=self.photo_instance
                ).values_list('plugin_id', flat=True)
                self.fields['excluded_plugins'].initial = excluded_ids
            
            # Add entity parameter fields for each valid plugin
            for plugin in valid_plugins:
                # Check if plugin has entity parameters defined
                try:
                    plugin_module = plugin._load_module()
                    if not plugin_module or not hasattr(plugin_module, '__plugin_entity_parameters__'):
                        continue
                    
                    entity_param_defs = plugin_module.__plugin_entity_parameters__
                    if not entity_param_defs:
                        continue
                except Exception:
                    continue
                
                field_name = f'entity_params_{plugin.pk}'
                
                # Get existing parameters if they exist
                initial_value = ""
                if self.photo_instance and self.photo_instance.pk:
                    try:
                        entity_params = PluginEntityParameters.objects.get(
                            plugin=plugin,
                            entity_uuid=self.photo_instance.uuid
                        )
                        initial_value = entity_params.parameters
                    except PluginEntityParameters.DoesNotExist:
                        pass
                
                # Build help text from entity parameter definitions
                help_text = "Available parameters (K: V format): " + ", ".join(entity_param_defs.keys())
                
                self.fields[field_name] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={'rows': 3, 'class': 'textarea textarea-bordered w-full'}),
                    label=f"Entity Parameters for {plugin}",
                    help_text=help_text,
                    initial=initial_value
                )
        except Exception:
            # If integration app is not available, use empty queryset
            from django.db.models import Model
            self.fields['excluded_plugins'].queryset = Model.objects.none()

    def clean(self):
        """Validate entity parameter fields."""
        cleaned_data = super().clean()
        
        # Validate each entity parameter field
        # Use list() to create a copy of items to avoid RuntimeError during iteration
        for field_name, value in list(cleaned_data.items()):
            if field_name.startswith('entity_params_') and value:
                # Validate format
                seen_keys = set()
                for line in value.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if ':' not in line:
                        self.add_error(field_name, f"Invalid format: '{line}'. Expected 'key: value'.")
                        continue
                    key = line.split(':', 1)[0].strip()
                    if key in seen_keys:
                        self.add_error(field_name, f"Duplicate key: '{key}'")
                    seen_keys.add(key)
        
        return cleaned_data

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
    
    def setup_entity_parameters(self, photo):
        """
        Set up entity parameters for a photo based on form data.
        Must be called after the photo has been saved and has an ID.
        """
        # Process each entity parameter field
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('entity_params_'):
                plugin_id = int(field_name.replace('entity_params_', ''))
                
                try:
                    plugin = PythonPlugin.objects.get(pk=plugin_id)
                    
                    if value and value.strip():
                        # Create or update entity parameters
                        PluginEntityParameters.objects.update_or_create(
                            plugin=plugin,
                            entity_uuid=photo.uuid,
                            defaults={'parameters': value}
                        )
                    else:
                        # Delete if empty
                        PluginEntityParameters.objects.filter(
                            plugin=plugin,
                            entity_uuid=photo.uuid
                        ).delete()
                except PythonPlugin.DoesNotExist:
                    pass
