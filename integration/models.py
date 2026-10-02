from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.timezone import now, datetime
import os
import uuid
import logging
from io import StringIO
from typing import Optional
from media.models import Channel
from .services import load_plugin_module

    
class IntegrationCaller(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    EVENT_SCHEDULER = "EVENT_SCHEDULER", "Event Scheduler"


class PluginStorage(models.Model):
    """
    Key-value storage for integration plugins to persist data.
    Keys are automatically prefixed with plugin UUID.
    """
    key = models.CharField(max_length=512, unique=True, db_index=True)
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integration Persistent Storage"
        verbose_name_plural = "Integration Persistent Storage"

    def __str__(self):
        return f"{self.key}: {str(self.value)[:50]}"


class IntegrationPlugin(models.Model):
    """Integration Plugin"""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nickname = models.CharField(max_length=255, blank=True, null=True, help_text="Optional")
    active = models.BooleanField(default=True)
    module = models.CharField(max_length=255, help_text="Python module name (without .py extension)")
    config = models.JSONField(blank=True, null=True, default=dict, help_text="JSON object containing plugin configuration with environment variable support")
    channel = models.ForeignKey(Channel, on_delete=models.SET_NULL, null=True, blank=True, help_text="Subscribe to a photo publication channel.")
    storage_prefix = models.CharField(max_length=255, blank=True, null=True, help_text="Optional prefix for persistent storage keys; use if multiple instances of the same plugin module.")

    def _load_module(self):
        """Load the integration module from the configured plugin paths."""
        return load_plugin_module(self.module)
    
    def _get_plugin_class(self, module):
        """Find the PhotoservPlugin subclass in the module."""
        from photoserv_plugin import PhotoservPlugin
        
        for item_name in dir(module):
            item = getattr(module, item_name)
            if isinstance(item, type) and issubclass(item, PhotoservPlugin) and item is not PhotoservPlugin:
                return item
        return None
    
    def _get_config_dict(self) -> dict:
        """Get config dictionary with environment variables expanded."""
        if not self.config:
            return {}
        
        def expand_env_vars(obj):
            """Recursively expand environment variables in strings."""
            if isinstance(obj, str):
                return os.path.expandvars(obj)
            elif isinstance(obj, dict):
                return {k: expand_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [expand_env_vars(item) for item in obj]
            else:
                return obj
        
        return expand_env_vars(self.config)
    
    def _run(self, **kwargs) -> str:
        """
        Run a specific plugin method.
        
        Kwargs:
            method_name: Name of the method to call (defaults to 'register')
            method_args: Tuple of arguments to pass to the method
            
        Returns:
            Log output from the plugin execution
        """
        method_name = kwargs.get('method_name', 'register')
        method_args = kwargs.get('method_args', ())
        
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        
        plugin_logger = logging.getLogger(f'plugin.{self.module}')
        plugin_logger.setLevel(logging.DEBUG)
        plugin_logger.handlers.clear()
        plugin_logger.addHandler(handler)
        
        try:
            # Load the module
            plugin_module = self._load_module()
            if plugin_module is None:
                raise Exception(f"Plugin module '{self.module}' not found")
            
            # Get the plugin class
            plugin_class = self._get_plugin_class(plugin_module)
            if plugin_class is None:
                raise Exception(f"No PhotoservPlugin subclass found in '{self.module}'")
            
            # Prepare config and photoserv instance
            config_dict = self._get_config_dict()
            from photoserv_plugin import PhotoservInstance
            photoserv_instance = PhotoservInstance(
                plugin_uuid=str(self.uuid),
                storage_prefix=self.storage_prefix,
                logger=plugin_logger
            )
            
            # Instantiate the plugin (calls __init__ with config and photoserv)
            plugin_instance = plugin_class(config_dict, photoserv_instance)
            
            # Log plugin info
            plugin_logger.info(f"Plugin: {plugin_module.__plugin_name__}")
            plugin_logger.info(f"Version: {plugin_module.__plugin_version__}")
            plugin_logger.info(f"UUID: {plugin_module.__plugin_uuid__}")
            plugin_logger.info(f"Config: {list(config_dict.keys())}")
            
            # Call the requested method
            if method_name == 'register':
                # Already registered in __init__, just log success
                plugin_logger.info("Plugin initialized successfully")
            else:
                method = getattr(plugin_instance, method_name, None)
                if method is None:
                    raise Exception(f"Method '{method_name}' not found in plugin")
                
                plugin_logger.info(f"Calling {method_name}")
                method(*method_args)
            
            plugin_logger.info(f"{method_name} completed successfully")
            
        except Exception as e:
            plugin_logger.error(f"Error in {method_name}: {str(e)}")
            raise
        finally:
            handler.flush()
            plugin_logger.removeHandler(handler)
        
        return log_stream.getvalue()

    def run(self, caller: IntegrationCaller, **kwargs):
        """Execute the integration and automatically record the result."""
        result = RunResult.objects.create(
            integration_plugin=self,
            start_timestamp=now(),
            caller=caller,
        )

        try:
            log_output = self._run(**kwargs)
            result.successful = True
            result.run_log = log_output
        except Exception as e:
            result.successful = False
            result.run_log = f"ERROR: {e}"
        finally:
            result.run_log = result.run_log.strip()
            result.end_timestamp = now()
            result.save()

        return result

    @property
    def run_history(self):
        """Query run history for this integration instance."""
        return self.run_results.order_by('-start_timestamp')
    
    @property
    def last_run_timestamp(self) -> Optional[datetime]:
        """Get the most recent run result for this integration instance."""
        last_run = self.run_results.order_by('-start_timestamp').first()
        return last_run.start_timestamp if last_run else None

    @property
    def valid(self) -> bool:
        """Check if the plugin module exists and is valid."""
        try:
            plugin_module = self._load_module()
            if plugin_module is None:
                return False
            
            # Check for required module-level variables
            required_attrs = ['__plugin_name__', '__plugin_uuid__', '__plugin_version__', '__plugin_config__']
            for attr in required_attrs:
                if not hasattr(plugin_module, attr):
                    return False
            
            # Check if module has a PhotoservPlugin subclass
            from photoserv_plugin import PhotoservPlugin
            plugin_class = self._get_plugin_class(plugin_module)
            return plugin_class is not None
        except Exception:
            return False

    def clean(self):
        """Validate config format."""
        if self.config:
            if not isinstance(self.config, dict):
                raise ValidationError("Config must be a valid JSON object.")

    def __str__(self):
        return self.nickname if self.nickname else f"{self.module} ({str(self.uuid)[:8]})"
    
    def get_absolute_url(self):
        return reverse("integration-plugin-detail", kwargs={"pk": self.pk})

    class Meta:
        verbose_name = "Integration Plugin"


class RunResult(models.Model):
    """
    Stores a historical record of an integration run.
    """
    integration_plugin = models.ForeignKey(IntegrationPlugin, on_delete=models.CASCADE, related_name='run_results', null=True)
    start_timestamp = models.DateTimeField(blank=True, null=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)
    caller = models.CharField(max_length=32, choices=IntegrationCaller.choices)
    successful = models.BooleanField(default=False)
    run_log = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-start_timestamp']

    def __str__(self):
        status = "PASS" if self.successful else "FAIL"
        return f"[{status}] {self.start_timestamp} to {self.end_timestamp} ({self.integration_plugin})"
    
    def get_absolute_url(self):
        return reverse("integration-run-result-detail", kwargs={"pk": self.pk})
