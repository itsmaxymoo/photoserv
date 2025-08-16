from django.urls import path

from .views import *

urlpatterns = [
    path("photos/", PhotoListView.as_view(), name="photo-list"),
    path("photos/new/", PhotoCreateView.as_view(), name="photo-create"),
    path("photos/<pk>/edit/", PhotoUpdateView.as_view(), name="photo-edit"),
    path("photos/<pk>/delete/", PhotoDeleteView.as_view(), name="photo-delete"),
    path("photos/<pk>/", PhotoDetailView.as_view(), name="photo-detail"),

    path("sizes/", SizeListView.as_view(), name="size-list"),
    path("sizes/new/", SizeCreateView.as_view(), name="size-create"),
    path("sizes/<int:pk>/edit/", SizeUpdateView.as_view(), name="size-edit"),
    path("sizes/<int:pk>/delete/", SizeDeleteView.as_view(), name="size-delete"),
]
