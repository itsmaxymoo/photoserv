"""
Example photoserv plugin demonstrating the plugin interface.

This plugin shows how to:
- Define configuration schema and entity parameter schema
- Access configuration values (provided as JSON in admin)
- Access per-entity parameters (provided as JSON per photo)
- Use persistent storage
- Handle photo publish/unpublish events
"""

from photoserv_plugin import PhotoservPlugin

# Required module-level variables
__plugin_name__ = "Example Plugin"
__plugin_uuid__ = "00000000-0000-0000-0000-000000000000"
__plugin_version__ = "0.1.0"

# Example configuration schema - describes what config this plugin expects
# Users will provide actual values as JSON in the admin interface, for example:
# {
#   "example_param": "some value",
#   "api_key": "${MY_API_KEY}",
#   "max_retries": 3,
#   "enabled_features": ["feature1", "feature2"]
# }
__plugin_config__ = {
    "example_param": "An example configuration parameter",
    "api_key": "An API key for external service (can use ${ENV_VAR} syntax)",
    "max_retries": "Maximum number of retry attempts (numeric value)",
    "enabled_features": "List of enabled features (array of strings)",
}

# Example entity parameter schema - describes per-entity parameters
# Users will provide actual values as JSON per photo, for example:
# {
#   "custom_field": "special_value",
#   "priority": 5,
#   "tags": ["important", "featured"]
# }
__plugin_entity_parameters__ = {
    "custom_field": "A custom field specific to this photo",
    "priority": "Priority level for this entity (numeric, e.g., 1-10)",
    "tags": "Array of tags to apply to this photo",
}


class ExamplePlugin(PhotoservPlugin):
    """Example plugin implementation."""
    
    def __init__(self, config, photoserv):
        """Initialize the plugin with configuration."""
        super().__init__(config, photoserv)
        
        # Plugin initialization logic
        # config is a dictionary with values from the JSON configuration
        self.logger.info(f"Plugin initialized with config keys: {list(config.keys())}")
        for key, value in config.items():
            self.logger.info(f"  {key}: {value} (type: {type(value).__name__})")
        
        # Access specific config values
        # These can be strings, numbers, booleans, lists, or nested objects
        api_key = config.get('api_key', 'not_set')
        max_retries = config.get('max_retries', 3)
        enabled_features = config.get('enabled_features', [])
        
        self.logger.info(f"API key configured: {'Yes' if api_key != 'not_set' else 'No'}")
        self.logger.info(f"Max retries: {max_retries}")
        self.logger.info(f"Enabled features: {enabled_features}")
        
        # Example: Store and retrieve from persistent storage
        call_count = self.photoserv.config.get('call_count', 0)
        self.logger.info(f"This plugin has been called {call_count} times")
        self.photoserv.config.set('call_count', call_count + 1)

    def on_global_change(self, **kwargs):
        """Handle global change events."""
        self.logger.info("Global change event received")
    
    def on_photo_publish(self, data, params, **kwargs):
        """Handle photo publish events."""
        # data is a dict with serialized data from the public API
        self.logger.info(f"Photo published: {data.get('title')} (UUID: {data.get('uuid')})")
        
        # params contains per-entity parameters configured for this photo
        # These are provided as JSON and can include various types
        if params:
            self.logger.info(f"  Entity parameters: {params}")
            
            # Access specific entity parameters
            custom_field = params.get('custom_field')
            priority = params.get('priority', 0)
            tags = params.get('tags', [])
            
            if custom_field:
                self.logger.info(f"  Custom field: {custom_field}")
            if priority > 0:
                self.logger.info(f"  Priority: {priority}")
            if tags:
                self.logger.info(f"  Tags: {', '.join(tags)}")
        
        # Example: Get a photo's thumbnail
        try:
            thumbnail = self.photoserv.get_photo_image(data, 'photoserv_ui_small')
            if thumbnail:
                self.logger.info(f"  Retrieved thumbnail image stream")
                thumbnail.close()
        except Exception as e:
            self.logger.error(f"  Error getting thumbnail: {e}")
    
    def on_photo_unpublish(self, data, params, **kwargs):
        """Handle photo unpublish events."""
        # data is a dict with serialized data from the public API
        self.logger.info(f"Photo unpublished: {data.get('title')} (UUID: {data.get('uuid')})")
        
        # params contains per-entity parameters configured for this photo
        if params:
            self.logger.info(f"  Entity parameters: {params}")
