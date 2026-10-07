from django.apps import AppConfig


class ApiKeyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_key'

    def ready(self):
        # Register the project's API-key OpenAPI security scheme once.
        from . import extensions  # noqa: F401
