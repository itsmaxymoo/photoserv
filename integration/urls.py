from django.urls import path

from .views import (
    IntegrationHomeView,
    IntegrationPluginCreateView,
    IntegrationPluginDeleteView,
    IntegrationPluginDetailView,
    IntegrationPluginListView,
    IntegrationPluginTestRunView,
    IntegrationPluginUpdateView,
    RunResultDeleteView,
    RunResultDetailView,
    RunResultListView,
)

urlpatterns = [
    path("", IntegrationHomeView.as_view(), name="integration-list"),

    path("runs/", RunResultListView.as_view(), name="integration-run-result-list"),
    path("runs/<pk>/", RunResultDetailView.as_view(), name="integration-run-result-detail"),
    path("runs/<pk>/delete/", RunResultDeleteView.as_view(), name="integration-run-result-delete"),

    path("plugins/", IntegrationPluginListView.as_view(), name="integration-plugin-list"),
    path("plugins/new", IntegrationPluginCreateView.as_view(), name="integration-plugin-create"),
    path("plugins/<pk>/edit/", IntegrationPluginUpdateView.as_view(), name="integration-plugin-edit"),
    path("plugins/<pk>/delete/", IntegrationPluginDeleteView.as_view(), name="integration-plugin-delete"),
    path("plugins/<pk>/test/", IntegrationPluginTestRunView.as_view(), name="integration-plugin-test-run"),
    path("plugins/<pk>/", IntegrationPluginDetailView.as_view(), name="integration-plugin-detail"),
]
