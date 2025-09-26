from rest_framework import viewsets
from core.models import Photo, Size
from .serializers import *
from django.http import FileResponse, Http404
from rest_framework.generics import GenericAPIView
from api_key.authentication import APIKeyAuthentication
from api_key.permissions import HasAPIKey
from rest_framework.response import Response
from .models import *


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
    queryset = Photo.objects.filter(hidden=False)

    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoSummarySerializer
        return PhotoSerializer


class PhotoImageAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    queryset = Photo.objects.all()
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


class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]
    lookup_field = 'uuid'
    queryset = Album.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AlbumSummarySerializer
        return AlbumSerializer


class SiteHealthAPIView(GenericAPIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey]

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
