from rest_framework.permissions import BasePermission


class HasAPIKey(BasePermission):
    """
    Allows access if APIKeyAuthentication succeeded, even if request.user is None.
    """
    def has_permission(self, request, view):
        return request.auth is not None
