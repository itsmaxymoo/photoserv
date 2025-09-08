from django.conf import settings
import core
from photoserv import settings


def global_context(request):
    return {
        "UI_THUMBNAIL_SIZE": core.UI_THUMBNAIL_SIZE,
        "SIMPLE_AUTH_ENABLED": settings.SIMPLE_AUTH,
        "OIDC_AUTH_ENABLED": settings.OIDC_ENABLED,
        "OIDC_PROVIDER_NAME": settings.OIDC_NAME,
        "AUTH_ENABLED": settings.AUTH_ENABLED,
    }
