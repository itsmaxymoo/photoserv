import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated


FULL_API_ACCESS_PERMISSION = "media.full_api_access"


def has_internal_identifier_access(request):
    """Return whether a request may expose and resolve database IDs."""

    if request is None:
        return False
    if isinstance(
        getattr(request, "successful_authenticator", None),
        SessionAuthentication,
    ):
        return True
    user = getattr(request, "user", None)
    return bool(
        user
        and user.is_authenticated
        and user.has_perm(FULL_API_ACCESS_PERMISSION)
    )


def scope_queryset_for_api_access(queryset, request):
    """Limit private media records for API-key users without full access."""

    if has_internal_identifier_access(request):
        return queryset

    model_name = queryset.model._meta.model_name
    visibility_filters = {
        "photo": {
            "channels__channel__builtin": True,
            "channels__published": True,
        },
        "channel": {"builtin": True},
        "size": {"public": True},
        "photosize": {"size__public": True},
        "channelphoto": {
            "channel__builtin": True,
            "published": True,
        },
    }
    filters = visibility_filters.get(model_name)
    if filters is None:
        return queryset
    queryset = queryset.filter(**filters)
    return queryset.distinct() if model_name == "photo" else queryset


def get_public_entity(queryset, identifier, request):
    """Resolve a PublicEntity by UUID, then by ID for trusted requests."""

    queryset = scope_queryset_for_api_access(queryset, request)

    try:
        entity_uuid = uuid.UUID(str(identifier))
    except (AttributeError, TypeError, ValueError):
        entity_uuid = None

    if entity_uuid is not None:
        try:
            return queryset.get(uuid=entity_uuid)
        except queryset.model.DoesNotExist:
            pass

    if has_internal_identifier_access(request):
        try:
            entity_id = int(identifier)
        except (TypeError, ValueError):
            entity_id = None
        if entity_id is not None and entity_id > 0:
            return queryset.get(pk=entity_id)

    raise queryset.model.DoesNotExist


class ViewDjangoModelPermissions(DjangoModelPermissions):
    """Django model permissions including the standard ``view`` permission."""

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
    }


class MediaAPIViewSetMixin:
    """Shared authorization and public-entity lookup behavior for media APIs."""

    permission_classes = [IsAuthenticated, ViewDjangoModelPermissions]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def filter_queryset(self, queryset):
        queryset = scope_queryset_for_api_access(queryset, self.request)
        return super().filter_queryset(queryset)

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        identifier = self.kwargs[self.lookup_url_kwarg or self.lookup_field]
        try:
            obj = get_public_entity(queryset, identifier, self.request)
        except ObjectDoesNotExist as error:
            raise Http404 from error
        self.check_object_permissions(self.request, obj)
        return obj
