import mimetypes

from django.http import FileResponse, Http404
from django.db import transaction
from django.db.models import Max, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from .api_access import (
    MediaAPIViewSetMixin,
    get_public_entity,
    scope_queryset_for_api_access,
)
from .filters import (
    AlbumFilter,
    ChannelFilter,
    ChannelPhotoFilter,
    PhotoAPIFilter,
    TagFilter,
)
from .models import (
    Album,
    Channel,
    ChannelPhoto,
    Photo,
    PhotoInAlbum,
    PhotoTag,
    Size,
    Tag,
)
from .serializers import (
    AlbumDetailSerializer,
    AlbumSerializer,
    ChannelDetailSerializer,
    ChannelPhotoRelationshipSerializer,
    ChannelSerializer,
    PhotoCreateSerializer,
    PhotoRelationshipSerializer,
    PhotoSerializer,
    PhotoUpdateSerializer,
    SizeSerializer,
    TagCreateSerializer,
    TagDetailSerializer,
    TagSerializer,
    TagUpdateSerializer,
)


def _relationship_value(request, key):
    """Allow DELETE clients to send relationship data in body or query string."""

    return request.data.get(key) or request.query_params.get(key)


class UUIDModelViewSet(MediaAPIViewSetMixin, viewsets.ModelViewSet):
    pass


class PhotoViewSet(UUIDModelViewSet):
    serializer_class = PhotoSerializer
    filterset_class = PhotoAPIFilter
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action == "create":
            return PhotoCreateSerializer
        if self.action in {"update", "partial_update"}:
            return PhotoUpdateSerializer
        return PhotoSerializer

    def get_queryset(self):
        queryset = (
            Photo.objects.select_related("metadata")
            .prefetch_related(
                "albums",
                "tags",
            )
            .order_by("uuid")
        )
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="size",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Size UUID or slug.",
            ),
        ],
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"sizes/(?P<size>[^/.]+)",
    )
    def size_image(self, request, uuid=None, size=None):
        photo = self.get_object()
        photo_size = None
        size_queryset = scope_queryset_for_api_access(Size.objects.all(), request)

        try:
            requested_size = get_public_entity(
                size_queryset,
                size,
                request,
            )
        except Size.DoesNotExist:
            requested_size = None

        if requested_size is not None:
            photo_size = photo.sizes.filter(
                size=requested_size,
            ).first()
        if photo_size is None:
            photo_size = scope_queryset_for_api_access(
                photo.sizes.all(),
                request,
            ).filter(
                size__slug=size,
            ).first()
        if photo_size is None or not photo_size.image:
            raise Http404("Requested size not found.")

        content_type = (
            mimetypes.guess_type(photo_size.image.name)[0]
            or "application/octet-stream"
        )
        return FileResponse(photo_size.image.open("rb"), content_type=content_type)


class AlbumViewSet(UUIDModelViewSet):
    filterset_class = AlbumFilter

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AlbumDetailSerializer
        return AlbumSerializer

    def get_queryset(self):
        return (
            Album.objects.select_related("parent")
            .prefetch_related("children", "_photos__sizes__size")
            .order_by("uuid")
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="recursive",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                default=False,
            ),
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        methods=["POST"],
        request=PhotoRelationshipSerializer,
        responses=AlbumDetailSerializer,
    )
    @extend_schema(
        methods=["DELETE"],
        parameters=[
            OpenApiParameter(
                name="photo",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=["post", "delete"], url_path="photo")
    @transaction.atomic
    def photos(self, request, uuid=None):
        album = self.get_object()
        raw_photo = _relationship_value(request, "photo")
        serializer = PhotoRelationshipSerializer(
            data={"photo": raw_photo},
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data["photo"]

        if request.method == "POST":
            maximum = PhotoInAlbum.objects.filter(album=album).aggregate(
                maximum=Max("order")
            )["maximum"]
            relationship, created = PhotoInAlbum.objects.get_or_create(
                album=album,
                photo=photo,
                defaults={"order": (maximum or 0) + 1},
            )
            album._prefetched_objects_cache = {}
            return Response(
                AlbumDetailSerializer(
                    album,
                    context=self.get_serializer_context(),
                ).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        get_object_or_404(PhotoInAlbum, album=album, photo=photo).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(
    MediaAPIViewSetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    filterset_class = TagFilter
    http_method_names = ["get", "post", "put", "delete", "head", "options"]
    queryset = Tag.objects.prefetch_related("photos__sizes__size").order_by(
        "name", "uuid"
    )

    def get_serializer_class(self):
        if self.action == "create":
            return TagCreateSerializer
        if self.action == "retrieve":
            return TagDetailSerializer
        if self.action == "update":
            return TagUpdateSerializer
        return TagSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="photo",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Remove this tag from one photo. If omitted, delete the tag."
                ),
            )
        ]
    )
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        tag = self.get_object()
        raw_photo = _relationship_value(request, "photo")
        if raw_photo:
            serializer = PhotoRelationshipSerializer(
                data={"photo": raw_photo},
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            photo = serializer.validated_data["photo"]
            get_object_or_404(PhotoTag, photo=photo, tag=tag).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)


class SizeViewSet(
    MediaAPIViewSetMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SizeSerializer
    filterset_fields = {
        "slug": ["exact", "icontains"],
        "max_dimension": ["exact", "gte", "lte"],
        "square_crop": ["exact"],
        "builtin": ["exact"],
        "can_edit": ["exact"],
        "public": ["exact"],
    }
    queryset = Size.objects.order_by("max_dimension", "uuid")


class ChannelViewSet(UUIDModelViewSet):
    filterset_class = ChannelFilter

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ChannelDetailSerializer
        return ChannelSerializer

    def get_queryset(self):
        memberships = scope_queryset_for_api_access(
            ChannelPhoto.objects.select_related("photo"),
            self.request,
        )
        if self.action == "retrieve":
            memberships = ChannelPhotoFilter(
                self.request.query_params,
                queryset=memberships,
                request=self.request,
            ).qs
        return (
            Channel.objects.prefetch_related(
                Prefetch("photos", queryset=memberships)
            )
            .order_by("uuid")
        )

    @extend_schema(
        methods=["POST"],
        request=ChannelPhotoRelationshipSerializer,
        responses=ChannelDetailSerializer,
    )
    @extend_schema(
        methods=["DELETE"],
        parameters=[
            OpenApiParameter(
                name="photo",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=True,
            )
        ],
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=["post", "delete"], url_path="photo")
    @transaction.atomic
    def photos(self, request, uuid=None):
        channel = self.get_object()
        if request.method == "POST":
            serializer = ChannelPhotoRelationshipSerializer(
                data=request.data,
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            photo = serializer.validated_data["photo"]
            publish_date = serializer.validated_data["publish_date"]
            if publish_date is None:
                publish_date = timezone.now()
            relationship, created = ChannelPhoto.objects.update_or_create(
                channel=channel,
                photo=photo,
                defaults={
                    "publish_date": publish_date,
                    "published": False,
                },
            )
            channel._prefetched_objects_cache = {}
            return Response(
                ChannelDetailSerializer(
                    channel,
                    context=self.get_serializer_context(),
                ).data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        raw_photo = _relationship_value(request, "photo")
        serializer = PhotoRelationshipSerializer(
            data={"photo": raw_photo},
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        photo = serializer.validated_data["photo"]
        get_object_or_404(ChannelPhoto, channel=channel, photo=photo).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
