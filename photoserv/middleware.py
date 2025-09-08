from django.conf import settings
from django.shortcuts import redirect
from photoserv.settings import SIMPLE_AUTH

class LoginRequiredMiddleware:
    """
    Middleware that requires a user to be authenticated to access any view.
    Exemptions can be set in settings.LOGIN_EXEMPT_URLS.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = [
            settings.LOGIN_URL.lstrip("/")
        ]
        if hasattr(settings, "LOGIN_EXEMPT_URLS"):
            self.exempt_urls += [u.lstrip("/") for u in settings.LOGIN_EXEMPT_URLS]

    def __call__(self, request):
        path = request.path_info.lstrip("/")

        # Bypass conditions
        if (not SIMPLE_AUTH) or path.startswith("api/"):
            return self.get_response(request)

        if not request.user.is_authenticated:
            if path not in self.exempt_urls:
                return redirect(settings.LOGIN_URL)
        return self.get_response(request)
