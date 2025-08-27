from rest_framework import viewsets
from core.models import Photo, Size
from .serializers import *
from rest_framework.response import Response


class SizeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SizeSerializer
    lookup_field = 'slug'
    queryset = Size.objects.all()


class PhotoViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'uuid'
    queryset = Photo.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoSummarySerializer
        return PhotoSerializer


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'uuid'
    queryset = Tag.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return TagSummarySerializer
        return TagSerializer

