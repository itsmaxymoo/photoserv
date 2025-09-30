from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public_rest_api'

    def ready(self):
        import public_rest_api.extensions
