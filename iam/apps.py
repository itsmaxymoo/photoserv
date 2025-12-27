from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.dispatch import receiver


class IamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'iam'

    def ready(self):
        from django.contrib.auth import get_user_model

        @receiver(post_migrate)
        def create_default_admin(sender, **kwargs):
            if sender.name != 'iam':
                return

            User = get_user_model()
            oidc_enabled = getattr(settings, "OIDC_ENABLED", False)
            simple_auth = getattr(settings, "SIMPLE_AUTH", False)

            if simple_auth and not oidc_enabled:
                if not User.objects.exists():
                    User.objects.create_superuser(
                        username="admin",
                        email="admin@localhost",
                        password="admin",
                    )
