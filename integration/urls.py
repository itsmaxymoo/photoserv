from django.urls import path

from .views import *

urlpatterns = [
    path("", IntegrationHomeView.as_view(), name="integration-list"),

    path("photo/<int:pk>", IntegrationPhotoView.as_view(), name="integration-photo"),

    path("runs/", redirect_to_home, name="web-request-list"),
    path("runs/<pk>/", RunResultDetailView.as_view(), name="integration-run-result-detail"),
    path("runs/<pk>/delete/", RunResultDeleteView.as_view(), name="integration-run-result-delete"),

    path("web-requests/", redirect_to_home, name="web-request-list"),
    path("web-requests/new", WebRequestCreateView.as_view(), name="web-request-create"),
    path("web-requests/queue-global", QueueGlobalIntegrationsView.as_view(), name="web-request-queue-global"),
    path("web-requests/<pk>/edit/", WebRequestUpdateView.as_view(), name="web-request-edit"),
    path("web-requests/<pk>/delete/", WebRequestDeleteView.as_view(), name="web-request-delete"),
    path("web-requests/<pk>/send/", WebRequestTestSendView.as_view(), name="web-request-test-send"),
    path("web-requests/<pk>/", WebRequestDetailView.as_view(), name="web-request-detail"),

    path("python-plugins/", PythonPluginListView.as_view(), name="python-plugin-list"),
    path("python-plugins/new", PythonPluginCreateView.as_view(), name="python-plugin-create"),
    path("python-plugins/scan", PythonPluginScanView.as_view(), name="python-plugin-scan"),
    path("python-plugins/<pk>/edit/", PythonPluginUpdateView.as_view(), name="python-plugin-edit"),
    path("python-plugins/<pk>/delete/", PythonPluginDeleteView.as_view(), name="python-plugin-delete"),
    path("python-plugins/<pk>/test/", PythonPluginTestRunView.as_view(), name="python-plugin-test-run"),
    path("python-plugins/<pk>/", PythonPluginDetailView.as_view(), name="python-plugin-detail"),
]
