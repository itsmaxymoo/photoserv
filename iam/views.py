from django.conf import settings
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from django.contrib.auth import views as auth_views
from django.urls import reverse
from photoserv.mixins import CRUDGenericMixin
from .models import User
from .permissions import group_permissions_by_app, permission_display_name
from .tables import GroupTable, UserTable
from .forms import GroupForm, UserForm


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        # Safely fetch settings, default to False if not present
        oidc_enabled = getattr(settings, "OIDC_ENABLED", False)
        simple_auth = getattr(settings, "SIMPLE_AUTH", False)

        # Both disabled -> redirect to /
        if not oidc_enabled and not simple_auth:
            return redirect(reverse("home"))

        # Only OIDC enabled -> redirect to OIDC login
        if oidc_enabled and not simple_auth:
            return redirect(reverse("oidc_authentication_init"))

        # SIMPLE_AUTH true (with or without OIDC) -> default LoginView
        return super().dispatch(request, *args, **kwargs)


class UserMixin(CRUDGenericMixin):
    object_type_name = "User"
    object_type_name_plural = "Users"
    object_url_name_slug = "user"
    edit_disclaimer = "OIDC users will have their properties overwritten upon login."


class UserListView(UserMixin, SingleTableView):
    model = User
    table_class = UserTable
    template_name = "generic_crud_list.html"


class UserDetailView(UserMixin, DetailView):
    model = User


class UserCreateView(UserMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('user-detail', kwargs={'pk': self.object.pk})


class UserUpdateView(UserMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('user-detail', kwargs={'pk': self.object.pk})


class UserDeleteView(UserMixin, DeleteView):
    model = User
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('user-list')


class GroupMixin(CRUDGenericMixin):
    pass


class GroupListView(GroupMixin, SingleTableView):
    model = Group
    table_class = GroupTable
    template_name = "generic_crud_list.html"


class GroupDetailView(GroupMixin, DetailView):
    model = Group
    template_name = "iam/group_detail.html"

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            "permissions__content_type"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        permission_groups = group_permissions_by_app(
            self.object.permissions.all()
        )
        for _, permissions in permission_groups:
            for permission in permissions:
                permission.display_name = permission_display_name(permission)
        context["permission_groups"] = permission_groups
        return context


class GroupCreateView(GroupMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = "iam/group_form.html"

    def get_success_url(self):
        return reverse("group-detail", kwargs={"pk": self.object.pk})


class GroupUpdateView(GroupMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = "iam/group_form.html"

    def get_success_url(self):
        return reverse("group-detail", kwargs={"pk": self.object.pk})


class GroupDeleteView(GroupMixin, DeleteView):
    model = Group
    template_name = "confirm_delete_generic.html"

    def get_success_url(self):
        return reverse("group-list")
