from .views import *
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('login/', LoginView.as_view(template_name='iam/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login/oidc/', include('mozilla_django_oidc.urls')),

    path("users/", UserListView.as_view(), name="user-list"),
    path("users/new/", UserCreateView.as_view(), name="user-create"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user-edit"),
    path("users/<int:pk>/delete/", UserDeleteView.as_view(), name="user-delete"),
]
