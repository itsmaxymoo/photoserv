from rest_framework.routers import DefaultRouter

from .viewsets import (
    AlbumViewSet,
    ChannelViewSet,
    PhotoViewSet,
    PublicShareViewSet,
    SizeViewSet,
    TagViewSet,
)


app_name = "media-api"

router = DefaultRouter()
router.register("photos", PhotoViewSet, basename="photo")
router.register("albums", AlbumViewSet, basename="album")
router.register("tags", TagViewSet, basename="tag")
router.register("sizes", SizeViewSet, basename="size")
router.register("channels", ChannelViewSet, basename="channel")
router.register(
    "public-shares",
    PublicShareViewSet,
    basename="public-share",
)

urlpatterns = router.urls
