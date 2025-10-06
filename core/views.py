from django.urls import reverse
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from django.db.models import Count
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
    formset_support = True


class PhotoListView(PhotoMixin, SingleTableView):
    model = Photo
    table_class = PhotoTable
    template_name = "generic_crud_list.html"


class PhotoDetailView(DetailView):
    model = Photo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_sizes = Size.objects.all().order_by('max_dimension')
        photo_sizes = {ps.size_id: ps for ps in self.object.sizes.all()}
        context['sizes'] = [
            (size, photo_sizes.get(size.id)) for size in all_sizes
        ]
        return context


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
    template_name = "core/photo_form.html"

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoCreateMultipleView(PhotoMixin, View):
    template_name = "core/photo_formset.html"

    def get(self, request, *args, **kwargs):
        formset = PhotoFormSet(queryset=Photo.objects.none())  # empty forms
        return render(request, self.template_name, {"formset": formset})

    def post(self, request, *args, **kwargs):
        formset = PhotoFormSet(request.POST, request.FILES, queryset=Photo.objects.none())
        if formset.is_valid():
            formset.save()
            return redirect(reverse("photo-list"))
        return render(request, self.template_name, {"formset": formset})


class PhotoUpdateView(PhotoMixin, UpdateView):
    model = Photo
    form_class = PhotoForm
    template_name = "core/photo_form.html"

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

        table = PhotoListTable(ordered_photos)

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
    template_name = "core/album_form.html"

    def form_valid(self, form):
        # Save the Album itself first
        response = super().form_valid(form)

        # Update photo order from submitted hidden inputs
        photo_ids = [int(pid) for pid in self.request.POST.getlist("photo_order[]") if pid]
        for idx, photo_id in enumerate(photo_ids, start=1):
            PhotoInAlbum.objects.filter(album=self.object, photo_id=photo_id).update(order=idx)


        return response

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumDeleteView(AlbumMixin, DeleteView):
    model = Album
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('album-list')

#endregion

#region Tags

class TagMixin(CRUDGenericMixin):
    object_type_name = "Tag"
    object_type_name_plural = "Tags"
    object_url_name_slug = "tag"
    edit_disclaimer = "Renaming a tag will update all photos that use this tag. Deleting a tag will remove it from all photos."
    can_directly_create = False  # Tags are managed through the photo form, not directly


class TagListView(TagMixin, SingleTableView):
    model = Tag
    template_name = "generic_crud_list.html"
    table_class = TagTable

    def get_queryset(self):
        return Tag.objects.annotate(photo_count=Count("photos"))


class TagDetailView(DetailView):
    model = Tag

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        photos = Photo.objects.filter(tags=self.object).distinct()

        table = PhotoListTable(photos)

        context["photo_table"] = table
        return context


class TagUpdateView(TagMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('tag-detail', kwargs={'pk': self.object.pk})


class TagDeleteView(TagMixin, DeleteView):
    model = Tag
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('tag-list')

#endregion