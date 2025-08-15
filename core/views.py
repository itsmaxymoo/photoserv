from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, HttpResponseRedirect
from .models import Photo, Size
from .forms import PhotoForm, SizeForm
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

#region Sizes


def size_list(request):
    sizes = Size.objects.all()
    template = "core/size_table.html" if request.htmx else "core/size_list.html"
    return render(request, template, {"sizes": sizes})


def size_edit(request, pk):
    size = get_object_or_404(Size, pk=pk)
    if size.builtin:
        return render(request, "core/partials/size_row.html", {"size": size})

    if request.method == "POST":
        form = SizeForm(request.POST, instance=size)
        if form.is_valid():
            form.save()
            return render(request, "core/partials/size_row.html", {"size": size})
    else:
        form = SizeForm(instance=size)
    return render(request, "core/partials/size_form.html", {"form": form, "size": size})


def size_create(request):
    if request.method == "POST":
        form = SizeForm(request.POST)
        if form.is_valid():
            size = form.save()
            return render(request, "core/partials/size_row.html", {"size": size})
        return render(request, "core/partials/size_form.html", {"form": form, "size": None})
    else:  # GET -> return blank form
        form = SizeForm()
        return render(request, "core/partials/size_form.html", {"form": form, "size": None})


@require_http_methods(["POST"])
def size_delete(request, pk):
    size = get_object_or_404(Size, pk=pk)
    if request.method == "POST" and not size.builtin:
        size.delete()

        return HttpResponse(status=200)  # empty response triggers HTMX remove
    return HttpResponse(status=400)

#endregion