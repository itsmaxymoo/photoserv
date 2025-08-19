from django.urls import reverse
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from .models import *
from .forms import *
from .tables import *
from .mixins import CRUDGenericMixin
from django.http import FileResponse, Http404

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


class PhotoImageView(DetailView):
    model = Photo

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        size = kwargs.get('size')
        try:
            image_file = self.object.get_size(size).image
        except (AttributeError, KeyError, FileNotFoundError):
            raise Http404("Requested size not found.")
        if not image_file or not hasattr(image_file, 'open'):
            raise Http404("Image not available.")
        return FileResponse(image_file.open('rb'), content_type='image/jpeg')


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

#region Sizes


class SizeMixin(CRUDGenericMixin):
    object_type_name = "Size"
    object_type_name_plural = "Sizes"
    object_url_name_slug = "size"
    no_object_detail_page = True  # Sizes do not have a detail page
    edit_disclaimer = "Creating or modifying any size will trigger a reprocessing of all photos that use this size. This may take some time depending on the number of photos and sizes involved."


class SizeListView(SizeMixin, SingleTableView):
    model = Size
    template_name = "generic_crud_list.html"
    table_class = SizeTable  # No table for sizes yet


class SizeCreateView(SizeMixin, CreateView):
    model = Size
    form_class = SizeForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('size-list')


class SizeUpdateView(SizeMixin, UpdateView):
    model = Size
    form_class = SizeForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('size-list')


class SizeDeleteView(SizeMixin, DeleteView):
    model = Size
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('size-list')


#endregion

#region Albums


class AlbumMixin(CRUDGenericMixin):
    object_type_name = "Album"
    object_type_name_plural = "Albums"
    object_url_name_slug = "album"


class AlbumDetailView(DetailView):
    model = Album

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ordered_photos = self.object.get_ordered_photos()

        table = PhotoInAlbumTable(ordered_photos)

        context["photo_table"] = table
        return context


class AlbumListView(AlbumMixin, SingleTableView):
    model = Album
    template_name = "generic_crud_list.html"
    table_class = AlbumTable


class AlbumCreateView(AlbumMixin, CreateView):
    model = Album
    form_class = AlbumForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumUpdateView(AlbumMixin, UpdateView):
    model = Album
    form_class = AlbumForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumDeleteView(AlbumMixin, DeleteView):
    model = Album
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('album-list')

#endregion