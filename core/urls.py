from django.urls import path

from .views import *

urlpatterns = [
    path("photos/", PhotoListView.as_view(), name="photo-list"),
    path("photos/new/", PhotoCreateView.as_view(), name="photo-create"),
    path("photos/<pk>/edit/", PhotoUpdateView.as_view(), name="photo-edit"),
    path("photos/<pk>/delete/", PhotoDeleteView.as_view(), name="photo-delete"),
    path("photos/<pk>/", PhotoDetailView.as_view(), name="photo-detail"),

    path("sizes/", size_list, name="size-list"),
    path("sizes/new/", size_create, name="size-create"),
    path("sizes/<int:pk>/edit/", size_edit, name="size-edit"),
    path("sizes/<int:pk>/delete/", size_delete, name="size-delete"),
]
