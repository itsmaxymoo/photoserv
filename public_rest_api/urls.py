from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import *

router = DefaultRouter()
router.register(r'photos', PhotoViewSet, basename='photo')
router.register(r'sizes', SizeViewSet, basename='size')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'albums', AlbumViewSet, basename='album')

urlpatterns = [
    path("", include((router.urls, "api"), namespace="api")),
    path("photos/<uuid:uuid>/sizes/<slug:size>/", PhotoImageAPIView.as_view(), name="photo-image")
]
