from rest_framework import viewsets
from core.models import Photo, Size
from .serializers import *
from django.http import FileResponse, Http404
from rest_framework.generics import GenericAPIView
from api_key.authentication import APIKeyAuthentication
from api_key.permissions import HasAPIKey
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from .models import *


INCLUDE_SIZES_PARAM = OpenApiParameter(
    name='include_sizes',
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    description='Include photo sizes in the response (default: false)',
    required=False,
)


class SizeViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    serializer_class = SizeSerializer
    lookup_field = 'slug'
    queryset = Size.objects.filter(public=True)


class PhotoViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Photo.objects.filter(_published=True)

    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoSummarySerializer
        return PhotoSerializer
    
    @extend_schema(
        parameters=[INCLUDE_SIZES_PARAM],
        responses={200: PhotoSummarySerializer},
    )
    def list(self, request, *args, **kwargs):
        """
        List public photos.
        Optionally include sizes with ?include_sizes=true.
        """
        return super().list(request, *args, **kwargs)


class PhotoImageAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    queryset = Photo.objects.filter(_published=True)
    lookup_field = "uuid"

    def get(self, request, uuid, size, *args, **kwargs):
        photo = self.get_object()  # GenericAPIView uses queryset + lookup_field
        photo_size = photo.get_size(size)

        if not photo_size or not hasattr(photo_size.image, "open") or not photo_size.size.public:
            raise Http404("Requested size not found.")

        return FileResponse(photo_size.image.open("rb"), content_type="image/jpeg")


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Tag.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return TagSummarySerializer
        return TagSerializer

    @extend_schema(
        parameters=[INCLUDE_SIZES_PARAM],
        responses={200: TagSerializer},
        description="Retrieve a tag and its associated photos."
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get a tag by UUID.
        """
        return super().retrieve(request, *args, **kwargs)


class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Album.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumSummarySerializer
        return AlbumSerializer

    @extend_schema(
        parameters=[INCLUDE_SIZES_PARAM],
        responses={200: AlbumSerializer},
        description="Retrieve an album including metadata, children, and photos."
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Get an album by UUID.
        """
        return super().retrieve(request, *args, **kwargs)


class SiteHealthAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    serializer_class = SiteHealthSerializer

    def get(self, request, *args, **kwargs):
        from core.models import Photo, PhotoSize

        total_photos = Photo.objects.count()
        total_sizes = Size.objects.count()

        expected_sizes = total_photos * total_sizes
        actual_sizes = PhotoSize.objects.count()
        pending_sizes = expected_sizes - actual_sizes

        photos_with_all_sizes = (
            Photo.objects.annotate(size_count=models.Count("sizes"))
            .filter(size_count=total_sizes)
            .count()
        )

        photos_pending_sizes = total_photos - photos_with_all_sizes
        pending_metadata = Photo.objects.filter(metadata__isnull=True).count()

        site_health = SiteHealth(
            total_photos=total_photos,
            photos_pending_sizes=photos_pending_sizes,
            pending_sizes=pending_sizes,
            pending_metadata=pending_metadata,
        )

        serializer = SiteHealthSerializer(site_health)
        return Response(serializer.data)
