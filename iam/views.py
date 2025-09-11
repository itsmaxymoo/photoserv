from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.urls import reverse


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        # Safely fetch settings, default to False if not present
        oidc_enabled = getattr(settings, "OIDC_ENABLED", False)
        simple_auth = getattr(settings, "SIMPLE_AUTH", False)

        # Both disabled -> redirect to /
        if not oidc_enabled and not simple_auth:
            return redirect("/")

        # Only OIDC enabled -> redirect to OIDC login
        if oidc_enabled and not simple_auth:
            return redirect(reverse("oidc_authentication_init"))

        # SIMPLE_AUTH true (with or without OIDC) -> default LoginView
        return super().dispatch(request, *args, **kwargs)
