import json

from django import forms

from .models import IntegrationPlugin
from .services import discover_plugin_modules


class IntegrationPluginForm(forms.ModelForm):
    config = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 10,
            "class": "textarea textarea-bordered w-full font-mono",
            "data-json-editor": "true",
        }),
        help_text="JSON object containing plugin configuration (environment variables like ${VAR} are supported)",
    )

    class Meta:
        model = IntegrationPlugin
        fields = [
            "nickname",
            "module",
            "storage_prefix",
            "config",
            "channel",
            "active",
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["module"].widget = forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "list": "integration-plugin-modules",
            "type": "search",
        })
        self.valid_plugin_modules = [
            module_name
            for module_name in discover_plugin_modules()
            if IntegrationPlugin(module=module_name).valid
        ]

        # Pre-populate config field with pretty-printed JSON
        if self.instance and self.instance.pk and self.instance.config:
            self.initial['config'] = json.dumps(self.instance.config, indent=2)
        elif 'initial' in kwargs and 'config' in kwargs['initial']:
            if isinstance(kwargs['initial']['config'], dict):
                self.initial['config'] = json.dumps(kwargs['initial']['config'], indent=2)
    
    def clean_config(self):
        """Validate and parse JSON config."""
        config_str = self.cleaned_data.get('config', '').strip()
        if not config_str:
            return {}
        
        try:
            config = json.loads(config_str)
            if not isinstance(config, dict):
                raise forms.ValidationError("Config must be a JSON object (dictionary), not a list or other type.")
            return config
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")
