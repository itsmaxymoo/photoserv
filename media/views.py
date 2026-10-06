from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib import messages
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django_tables2.views import SingleTableView
from django_tables2 import RequestConfig
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, QueryDict
from django.utils import timezone
from urllib.parse import urlencode
import secrets
from datetime import datetime
from .models import *
from .forms import *
from .tables import *
from .filters import PhotoFilter
from . import services
from photoserv.mixins import CRUDGenericMixin
import calendar
from collections import defaultdict
import json

#region Photo

class PhotoListView(CRUDGenericMixin, FilterView, SingleTableView):
    model = Photo
    table_class = PhotoTable
    template_name = "media/photo_list.html"
    filterset_class = PhotoFilter

    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return (
            queryset.select_related('metadata')
            .prefetch_related('albums', 'tags')
            .annotate(
                configured_channel_count=Count('channels'),
                published_channel_count=Count(
                    'channels',
                    filter=Q(channels__published=True),
                ),
            )
            .order_by('-canonical_publish_date', 'pk')
        )


class PhotoDetailView(CRUDGenericMixin, DetailView):
    model = Photo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_sizes = Size.objects.all().order_by('max_dimension')
        photo_sizes = {ps.size_id: ps for ps in self.object.sizes.all()}
        context['sizes'] = [
            (size, photo_sizes.get(size.id)) for size in all_sizes
        ]
        channel_photos = {
            channel_photo.channel_id: channel_photo
            for channel_photo in ChannelPhoto.objects.filter(photo=self.object)
        }
        context['publishing_channels'] = [
            (channel, channel_photos.get(channel.pk))
            for channel in Channel.objects.all().order_by('name')
        ]
        context['now'] = timezone.now()
        context['custom_attributes'] = json.dumps(self.object.custom_attributes or {}, indent=2)
        return context


class PhotoImageView(PermissionRequiredMixin, DetailView):
    permission_required = "media.view_photo"
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


class PhotoCreateView(CRUDGenericMixin, CreateView):
    model = Photo
    form_class = PhotoForm
    template_name = "media/photo_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'photo_channel_form' not in context:
            context['photo_channel_form'] = PhotoChannelForm(
                self.request.POST if self.request.method == 'POST' else None,
                canonical_publish_date=(
                    context['form'].initial.get('canonical_publish_date')
                    or context['form'].fields['canonical_publish_date'].initial
                ),
            )

        return context

    def form_valid(self, form):
        photo_channel_form = PhotoChannelForm(
            self.request.POST,
            canonical_publish_date=form.cleaned_data.get('canonical_publish_date'),
        )
        if not photo_channel_form.is_valid():
            context = self.get_context_data(form=form)
            context['photo_channel_form'] = photo_channel_form
            return self.render_to_response(context)
        
        # Save with exclusion form
        self.object = form.save(commit=True)
        photo_channel_form.save(self.object)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoCalendarView(CRUDGenericMixin, TemplateView):
    template_name = "media/photo_calendar.html"
    model = Photo

    all_channels_value = "all"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        # Parse month/year from GET params
        req = self.request
        try:
            year = int(req.GET.get("year", today.year))
            month = int(req.GET.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        # Calendar starting on Sunday
        cal = calendar.Calendar(firstweekday=6)
        month_dates = list(cal.itermonthdates(year, month))
        # Build contiguous weeks (list of 7-date lists)
        weeks_raw = [month_dates[i : i + 7] for i in range(0, len(month_dates), 7)]

        default_channel = Channel.get_default_channel()
        channels = Channel.objects.exclude(pk=default_channel.pk).order_by("name")
        selected_channel = req.GET.get("channel", str(default_channel.pk))
        show_channel_names = selected_channel == self.all_channels_value

        if not show_channel_names:
            try:
                selected_channel_id = int(selected_channel)
            except (TypeError, ValueError):
                selected_channel_id = default_channel.pk
                selected_channel = str(default_channel.pk)

            if not Channel.objects.filter(pk=selected_channel_id).exists():
                selected_channel_id = default_channel.pk
                selected_channel = str(default_channel.pk)

        range_start = month_dates[0]
        range_end = month_dates[-1]
        channel_photos_qs = (
            ChannelPhoto.objects.select_related("photo", "channel")
            .filter(publish_date__date__range=(range_start, range_end))
            .order_by("publish_date")
        )
        if not show_channel_names:
            channel_photos_qs = channel_photos_qs.filter(channel_id=selected_channel_id)

        # Group channel-specific publication dates by local date.
        photos_map = defaultdict(list)
        for channel_photo in channel_photos_qs:
            try:
                pd = timezone.localtime(channel_photo.publish_date).date()
            except Exception:
                # Fallback to naive date if timezone conversion fails
                pd = channel_photo.publish_date.date()
            photos_map[pd].append(channel_photo)

        # Build week/days data structure for template convenience
        weeks = []
        for week in weeks_raw:
            week_row = []
            for d in week:
                week_row.append({
                    'date': d,
                    'day': d.day,
                    'in_month': d.month == month,
                    'is_today': d == today,
                    'photos': photos_map.get(d, []),
                })
            weeks.append(week_row)

        # Prev/next month calculation
        if month == 1:
            prev_month, prev_year = 12, year - 1
        else:
            prev_month, prev_year = month - 1, year
        if month == 12:
            next_month, next_year = 1, year + 1
        else:
            next_month, next_year = month + 1, year

        # Years dropdown population from channel publication dates.
        years_qs = ChannelPhoto.objects.dates('publish_date', 'year')
        years = sorted({d.year for d in years_qs})
        if not years:
            years = [today.year]

        context.update(
            {
                'weeks': weeks,
                'month': month,
                'year': year,
                'month_name': calendar.month_name[month],
                'prev_month': prev_month,
                'prev_year': prev_year,
                'next_month': next_month,
                'next_year': next_year,
                'years': years,
                'weekdays': ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
                'today': today,
                'channels': channels,
                'default_channel': default_channel,
                'selected_channel': selected_channel,
                'all_channels_value': self.all_channels_value,
                'show_channel_names': show_channel_names,
            }
        )
        return context

class PhotoUpdateView(CRUDGenericMixin, UpdateView):
    model = Photo
    form_class = PhotoForm
    template_name = "media/photo_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'photo_channel_form' not in context:
            context['photo_channel_form'] = PhotoChannelForm(
                self.request.POST if self.request.method == 'POST' else None,
                photo_instance=self.object,
            )
        return context

    def form_valid(self, form):
        photo_channel_form = PhotoChannelForm(self.request.POST, photo_instance=self.object)
        if not photo_channel_form.is_valid():
            context = self.get_context_data(form=form)
            context['photo_channel_form'] = photo_channel_form
            return self.render_to_response(context)
        
        # Save with exclusion form
        self.object = form.save(commit=True)
        photo_channel_form.save(self.object)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('photo-detail', kwargs={'pk': self.object.pk})


class PhotoDeleteView(CRUDGenericMixin, DeleteView):
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

class AlbumDetailView(CRUDGenericMixin, DetailView):
    model = Album

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ordered_photos = self.object.get_ordered_photos()
        table = PhotoListTable(ordered_photos)
        context["photo_table"] = table
        context['custom_attributes'] = json.dumps(self.object.custom_attributes or {}, indent=2)
        return context


class AlbumListView(CRUDGenericMixin, TemplateView):
    template_name = "media/album_list.html"
    model = Album

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build a parent->children mapping for all albums, sorted alphabetically
        all_albums = Album.objects.all().order_by('title')
        children_map = {}
        for a in all_albums:
            parent_id = a.parent_id
            children_map.setdefault(parent_id, []).append(a)

        def build_nodes(parent_id=None):
            nodes = []
            for a in children_map.get(parent_id, []):
                nodes.append({
                    'album': a,
                    'children': build_nodes(a.id)
                })
            return nodes

        context['album_tree'] = build_nodes(None)
        return context


class AlbumCreateView(CRUDGenericMixin, CreateView):
    model = Album
    form_class = AlbumForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('album-detail', kwargs={'pk': self.object.pk})


class AlbumUpdateView(CRUDGenericMixin, UpdateView):
    model = Album
    form_class = AlbumForm
    template_name = "media/album_form.html"

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


class AlbumDeleteView(CRUDGenericMixin, DeleteView):
    model = Album
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('album-list')

#endregion

#region Tags

class TagMixin(CRUDGenericMixin):
    edit_disclaimer = "Renaming a tag will update all photos that use this tag. Deleting a tag will remove it from all photos."
    can_directly_create = False


class TagListView(TagMixin, SingleTableView):
    model = Tag
    template_name = "generic_crud_list.html"
    table_class = TagTable

    def get_queryset(self):
        return Tag.objects.annotate(photo_count=Count("photos"))


class TagDetailView(TagMixin, DetailView):
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
        # If the tag was merged (and deleted), redirect to tag list
        if not Tag.objects.filter(pk=self.object.pk).exists():
            return reverse('tag-list')
        return reverse('tag-detail', kwargs={'pk': self.object.pk})


class TagDeleteView(TagMixin, DeleteView):
    model = Tag
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('tag-list')

#endregion

#region Channels

class ChannelPublicationHelperView(PermissionRequiredMixin, View):
    """Select filtered photos and prepare a channel-publication plan."""

    permission_required = (
        "media.view_channel",
        "media.view_photo",
        "media.add_channelphoto",
    )
    template_name = "media/channel_publication_helper.html"
    session_key = "channel_publication_helper_plans"

    @staticmethod
    def _filter_data(query_string):
        data = QueryDict(query_string or "", mutable=True)
        for key in ("channel", "page", "sort"):
            data.pop(key, None)
        return data

    @staticmethod
    def _ordered_photos(photo_filter):
        return photo_filter.qs.distinct().order_by("canonical_publish_date", "pk")

    def _initial_channel(self):
        channel_id = self.request.GET.get("channel")
        if channel_id:
            return Channel.objects.filter(pk=channel_id).first()
        return Channel.objects.order_by("name").first()

    def _render(self, form, photo_filter, filter_query):
        photos = self._ordered_photos(photo_filter)
        table = ChannelPublicationSelectionTable(photos)
        RequestConfig(self.request, paginate={"per_page": 5}).configure(table)
        channel = form["channel"].value() or self.request.GET.get("channel")
        helper_url = reverse("channel-publication-helper")
        start_value = form.fields["start_datetime"].widget.format_value(
            form["start_datetime"].value()
        )
        end_value = form.fields["end_datetime"].widget.format_value(
            form["end_datetime"].value()
        )
        time_start_value = form.fields["time_start"].widget.format_value(
            form["time_start"].value()
        )
        time_end_value = form.fields["time_end"].widget.format_value(
            form["time_end"].value()
        )
        return render(
            self.request,
            self.template_name,
            {
                "form": form,
                "filter": photo_filter,
                "filter_query": filter_query,
                "photo_table": table,
                "selected_photo_count": photos.count(),
                "channel_prefill": channel,
                "filter_clear_url": (
                    f"{helper_url}?{urlencode({'channel': channel})}"
                    if channel
                    else helper_url
                ),
                "start_value": start_value,
                "end_value": end_value,
                "time_start_value": time_start_value,
                "time_end_value": time_end_value,
            },
        )

    def get(self, request):
        filter_data = self._filter_data(request.GET.urlencode())
        filter_query = filter_data.urlencode()
        photo_filter = PhotoFilter(
            data=filter_data if filter_data else None,
            queryset=Photo.objects.all(),
        )
        form = ChannelPublicationHelperForm(
            channel=self._initial_channel(),
            initial={"filter_query": filter_query},
        )
        return self._render(form, photo_filter, filter_query)

    def post(self, request):
        form = ChannelPublicationHelperForm(request.POST)
        filter_query = request.POST.get("filter_query", "")
        filter_data = self._filter_data(filter_query)
        photo_filter = PhotoFilter(data=filter_data, queryset=Photo.objects.all())

        form_is_valid = form.is_valid()
        filter_is_valid = photo_filter.is_valid()
        if not filter_is_valid:
            form.add_error(None, "Correct the photo filter errors before continuing.")

        photos = list(self._ordered_photos(photo_filter)) if filter_is_valid else []
        if form_is_valid and not photos:
            form.add_error(None, "The current filter does not select any photos.")
            form_is_valid = False
        if not form_is_valid or not filter_is_valid:
            return self._render(form, photo_filter, filter_query)

        channel = form.cleaned_data["channel"]
        conflict_resolution = form.cleaned_data["conflict_resolution"]
        existing_photo_ids = set(
            ChannelPhoto.objects.filter(channel=channel, photo__in=photos)
            .values_list("photo_id", flat=True)
        )

        default_publications = {}
        if form.cleaned_data["respect_default_channel"]:
            default_channel = Channel.get_default_channel()
            if default_channel is not None:
                default_publications = {
                    channel_photo.photo_id: channel_photo
                    for channel_photo in ChannelPhoto.objects.filter(
                        channel=default_channel,
                        photo__in=photos,
                    ).order_by("pk")
                }

        entries = []
        scheduled_entries = []
        copied_count = 0
        for photo in photos:
            if photo.pk in existing_photo_ids:
                action = "republish" if conflict_resolution == "recreate" else "skip"
            else:
                action = "publish"
            entry = {
                "photo_id": photo.pk,
                "action": action,
                "publish_date": None,
                "date_source": None,
            }
            entries.append(entry)
            if action == "skip":
                continue

            default_publication = default_publications.get(photo.pk)
            if default_publication is not None and not default_publication.published:
                entry["publish_date"] = default_publication.publish_date.isoformat()
                entry["date_source"] = "default_channel"
                copied_count += 1
            else:
                scheduled_entries.append(entry)

        try:
            schedule = services.calculate_publication_schedule(
                len(scheduled_entries),
                form.cleaned_data["start_datetime"],
                form.cleaned_data["end_datetime"],
                form.cleaned_data["weekdays"],
                form.cleaned_data["time_start"],
                form.cleaned_data["time_end"],
                form.cleaned_data["jitter"],
            )
            rates = services.calculate_publication_rates(
                len(scheduled_entries),
                form.cleaned_data["start_datetime"],
                form.cleaned_data["end_datetime"],
                form.cleaned_data["weekdays"],
            )
        except ValueError as error:
            form.add_error(None, str(error))
            return self._render(form, photo_filter, filter_query)

        for entry, publish_date in zip(scheduled_entries, schedule):
            entry["publish_date"] = publish_date.isoformat()
            entry["date_source"] = "schedule"

        token = secrets.token_urlsafe(18)
        plans = request.session.get(self.session_key, {})
        if len(plans) >= 5:
            plans.pop(next(iter(plans)))
        plans[token] = {
            "channel_id": channel.pk,
            "filter_query": filter_query,
            "entries": entries,
            "scheduled_count": len(scheduled_entries),
            "copied_count": copied_count,
            "rates": {
                "per_day": rates.per_day,
                "per_week": rates.per_week,
                "per_month": rates.per_month,
                "eligible_days": rates.eligible_days,
            },
        }
        request.session[self.session_key] = plans
        confirmation_url = reverse("channel-publication-helper-confirm")
        return redirect(f"{confirmation_url}?{urlencode({'token': token})}")


class ChannelPublicationHelperConfirmView(PermissionRequiredMixin, View):
    """Preview and apply a server-side channel-publication plan."""

    permission_required = ChannelPublicationHelperView.permission_required
    template_name = "media/channel_publication_helper_confirm.html"
    session_key = ChannelPublicationHelperView.session_key

    def _get_plan(self, request):
        token = request.GET.get("token") or request.POST.get("token")
        return token, request.session.get(self.session_key, {}).get(token)

    def _discard_plan(self, request, token):
        plans = request.session.get(self.session_key, {})
        plans.pop(token, None)
        request.session[self.session_key] = plans

    def get(self, request):
        token, plan = self._get_plan(request)
        if not plan:
            messages.error(request, "That publication plan is missing or has expired.")
            return redirect("channel-publication-helper")

        channel = Channel.objects.filter(pk=plan["channel_id"]).first()
        if channel is None:
            self._discard_plan(request, token)
            messages.error(request, "The selected channel no longer exists.")
            return redirect("channel-publication-helper")

        photos = Photo.objects.in_bulk(entry["photo_id"] for entry in plan["entries"])
        rows = []
        action_labels = {
            "publish": "Publish",
            "republish": "Republish",
            "skip": "Skip",
        }
        for entry in plan["entries"]:
            photo = photos.get(entry["photo_id"])
            if photo is None:
                continue
            rows.append(
                {
                    "photo": photo,
                    "action": entry["action"],
                    "action_label": action_labels[entry["action"]],
                    "publish_date": (
                        datetime.fromisoformat(entry["publish_date"])
                        if entry["publish_date"]
                        else None
                    ),
                    "date_source": entry["date_source"],
                }
            )
        back_query = QueryDict(plan.get("filter_query", ""), mutable=True)
        back_query["channel"] = channel.pk
        back_url = (
            f"{reverse('channel-publication-helper')}?{back_query.urlencode()}"
        )
        return render(
            request,
            self.template_name,
            {
                "token": token,
                "plan": plan,
                "channel": channel,
                "rows": rows,
                "back_url": back_url,
            },
        )

    def post(self, request):
        token, plan = self._get_plan(request)
        if not plan:
            messages.error(request, "That publication plan is missing or has expired.")
            return redirect("channel-publication-helper")

        channel = Channel.objects.filter(pk=plan["channel_id"]).first()
        if channel is None:
            self._discard_plan(request, token)
            messages.error(request, "The selected channel no longer exists.")
            return redirect("channel-publication-helper")

        published = republished = skipped = 0
        with transaction.atomic():
            for entry in plan["entries"]:
                if entry["action"] == "skip":
                    skipped += 1
                    continue
                photo = Photo.objects.filter(pk=entry["photo_id"]).first()
                if photo is None:
                    skipped += 1
                    continue
                existing = ChannelPhoto.objects.filter(channel=channel, photo=photo)
                if entry["action"] == "publish" and existing.exists():
                    skipped += 1
                    continue
                if entry["action"] == "republish":
                    existing.delete()
                    republished += 1
                else:
                    published += 1
                ChannelPhoto.objects.create(
                    channel=channel,
                    photo=photo,
                    publish_date=datetime.fromisoformat(entry["publish_date"]),
                )

        self._discard_plan(request, token)
        messages.success(
            request,
            f"Published {published}, republished {republished}, and skipped {skipped} photos.",
        )
        return redirect("channel-detail", pk=channel.pk)

class ChannelListView(CRUDGenericMixin, SingleTableView):
    model = Channel
    template_name = "generic_crud_list.html"
    table_class = ChannelTable


class ChannelCreateView(CRUDGenericMixin, CreateView):
    model = Channel
    form_class = ChannelForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('channel-list')


class ChannelUpdateView(CRUDGenericMixin, UpdateView):
    model = Channel
    form_class = ChannelForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('channel-list')


class ChannelForkView(CRUDGenericMixin, FormView):
    model = Channel
    form_class = ChannelForkForm
    template_name = "generic_crud_form.html"
    permission_required = ("media.add_channel", "media.add_channelphoto")
    edit_disclaimer = (
        'Fork a channel, creating a new channel with the same photos published. '
        'This will not dispatch any integration handlers and is intended to be used '
        'for handling a diverging publication strategy. If "Include Future" is '
        'checked, the new channel will also include photos from the source channel '
        'that have not been published yet.'
    )

    def get_source_channel(self):
        if not hasattr(self, "source_channel"):
            self.source_channel = get_object_or_404(Channel, pk=self.kwargs["pk"])
        return self.source_channel

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["source_channel"] = self.get_source_channel()
        return kwargs

    def form_valid(self, form):
        self.object = services.fork_channel(
            self.get_source_channel(),
            form.cleaned_data["new_name"],
            include_future=form.cleaned_data["include_future"],
            new_description=form.cleaned_data["new_description"],
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("channel-detail", kwargs={"pk": self.object.pk})


class ChannelDeleteView(CRUDGenericMixin, DeleteView):
    model = Channel
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('channel-list')


class ChannelDetailView(CRUDGenericMixin, SingleTableMixin, DetailView):
    model = Channel
    table_class = ChannelPhotoTable

    def get_table_data(self):
        # Provide the queryset directly to django-tables2
        return self.object.photos.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_delete'] = not self.object.builtin
        return context

#endregion
