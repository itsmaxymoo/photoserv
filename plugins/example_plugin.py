"""
Example photoserv plugin demonstrating the plugin interface.
"""

from photoserv_plugin import PhotoservPlugin

# Required module-level variables
__plugin_name__ = "Example Plugin"
__plugin_uuid__ = "00000000-0000-0000-0000-000000000000"
__plugin_version__ = "1.0.0"
__plugin_config__ = {
    "example_param": "An example configuration parameter",
    "api_key": "An API key for external service (can use ${ENV_VAR})",
}


class ExamplePlugin(PhotoservPlugin):
    """Example plugin implementation."""
    
    def __init__(self, config, photoserv):
        """Initialize the plugin with configuration."""
        super().__init__(config, photoserv)
        
        # Plugin initialization logic
        self.logger.info(f"Plugin initialized with config keys: {list(config.keys())}")
        for key, value in config.items():
            self.logger.info(f"  {key}: {value}")
        
        # Example: Store and retrieve from persistent storage
        call_count = self.photoserv.config.get('call_count', 0)
        self.logger.info(f"This plugin has been called {call_count} times")
        self.photoserv.config.set('call_count', call_count + 1)

    def on_global_change(self):
        """Handle global change events."""
        self.logger.info("Global change event received")
    
    def on_photo_publish(self, data):
        """Handle photo publish events."""
        # data is a dict with serialized data from the public API
        self.logger.info(f"Photo published: {data.get('title')} (UUID: {data.get('uuid')})")
        
        # Example: Get a photo's thumbnail
        try:
            thumbnail = self.photoserv.get_photo_image(data, 'thumbnail')
            if thumbnail:
                self.logger.info(f"  Retrieved thumbnail image stream")
                thumbnail.close()
        except Exception as e:
            self.logger.error(f"  Error getting thumbnail: {e}")
    
    def on_photo_unpublish(self, data):
        """Handle photo unpublish events."""
        # data is a dict with serialized data from the public API
        self.logger.info(f"Photo unpublished: {data.get('title')} (UUID: {data.get('uuid')})")
