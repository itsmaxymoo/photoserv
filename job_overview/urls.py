from django.urls import path

from .views import *

urlpatterns = [
    path("jobs/", JobListView.as_view(), name="job-list"),
]
