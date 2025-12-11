from django.urls import path

from .views import *

urlpatterns = [
    path("", WebRequestListView.as_view(), name="integration-list"),

    path("web-requests/", redirect_to_home, name="web-request-list"),
    path("web-requests/new", WebRequestCreateView.as_view(), name="web-request-create"),
    path("web-requests/<pk>/edit/", WebRequestUpdateView.as_view(), name="web-request-edit"),
    path("web-requests/<pk>/delete/", WebRequestDeleteView.as_view(), name="web-request-delete"),
    path("web-requests/<pk>/send/", WebRequestTestSendView.as_view(), name="web-request-test-send"),
    path("web-requests/<pk>/", WebRequestDetailView.as_view(), name="web-request-detail"),
]
