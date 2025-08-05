from django.shortcuts import render
from django.urls import reverse
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from .models import Photo
from .forms import PhotoForm
from .tables import PhotoTable
from .mixins import CRUDGenericMixin

#region Photo

class PhotoMixin(CRUDGenericMixin):
    object_type_name = "Photo"
    object_type_name_plural = "Photos"
    object_url_name_slug = "photo"


class PhotoListView(PhotoMixin, SingleTableView):
    model = Photo
    table_class = PhotoTable
    template_name = "generic_crud_list.html"


class PhotoDetailView(DetailView):
    model = Photo


class PhotoCreateView(PhotoMixin, CreateView):
    model = Photo
    form_class = PhotoForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoUpdateView(PhotoMixin, UpdateView):
    model = Photo
    form_class = PhotoForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoDeleteView(DeleteView):
    model = Photo
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('photo-list')

#endregion