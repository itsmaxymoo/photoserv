from rest_framework.routers import DefaultRouter
from .views import *


router = DefaultRouter()
router.register(r'photos', PhotoViewSet, basename='photo')
router.register(r'sizes', SizeViewSet, basename='size')
router.register(r'tags', TagViewSet, basename='tag')
urlpatterns = router.urls
