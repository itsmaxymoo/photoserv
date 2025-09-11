from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError
from django.core.exceptions import ImproperlyConfigured


class IamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'iam'

    def ready(self):
        User = get_user_model()

        oidc_enabled = getattr(settings, "OIDC_ENABLED", False)
        simple_auth = getattr(settings, "SIMPLE_AUTH", False)

        # Only run if SIMPLE_AUTH enabled and OIDC disabled
        if simple_auth and not oidc_enabled:
            try:
                # Check if any users exist
                if User.objects.count() == 0:
                    # Create default admin user
                    User.objects.create_superuser(username="admin", email="admin@localhost", password="admin")
            except (OperationalError, ImproperlyConfigured):
                # Database might not be ready yet (e.g., during migrate)
                pass
