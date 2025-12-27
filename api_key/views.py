from django.shortcuts import render, redirect
from django.contrib import messages

from core.mixins import CRUDGenericMixin
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2 import SingleTableView
from .tables import APIKeyTable
from .forms import APIKeyForm
from .models import APIKey
from django.urls import reverse


# Create your views here.
class APIKeyMixin(CRUDGenericMixin):
    object_type_name = "API Key"
    object_type_name_plural = "API Keys"
    object_url_name_slug = "api-key"
    no_object_detail_page = True  # APIKeys do not have a detail page


class APIKeyListView(APIKeyMixin, SingleTableView):
    model = APIKey
    template_name = "api_key/api_key_list.html"
    table_class = APIKeyTable


class APIKeyCreateView(APIKeyMixin, CreateView):
    model = APIKey
    form_class = APIKeyForm
    template_name = "generic_crud_form.html"

    def form_valid(self, form):
        # Use your custom creation logic
        name = form.cleaned_data["name"]
        secret_key = APIKey.create_key(name)

        # Add success message with just the API key
        messages.success(self.request, secret_key)

        # Redirect manually — skip form.save() and super()
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("api-key-list")


class APIKeyUpdateView(APIKeyMixin, UpdateView):
    model = APIKey
    form_class = APIKeyForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('api-key-list')


class APIKeyDeleteView(APIKeyMixin, DeleteView):
    model = APIKey
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('api-key-list')
