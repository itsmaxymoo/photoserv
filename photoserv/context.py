from django.conf import settings
import core


def global_context(request):
    return {
        "UI_THUMBNAIL_SIZE": core.UI_THUMBNAIL_SIZE,
    }
