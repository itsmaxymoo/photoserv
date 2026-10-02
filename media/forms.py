from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from .models import *
from .tasks import post_photo_create
from datetime import time
import json


class FormWithCustomAttributesFieldMixin(forms.Form):
    custom_attributes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 10,
            'class': 'textarea textarea-bordered w-full font-mono',
            'data-json-editor': 'true'
        }),
        help_text="Specify any custom data (JSON format). Top level must be a dict/object."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate config field with pretty-printed JSON
        if self.instance and self.instance.pk and self.instance.custom_attributes:
            self.initial['custom_attributes'] = json.dumps(self.instance.custom_attributes, indent=2)
        elif 'initial' in kwargs and 'custom_attributes' in kwargs['initial']:
            if isinstance(kwargs['initial']['custom_attributes'], dict):
                self.initial['custom_attributes'] = json.dumps(kwargs['initial']['custom_attributes'], indent=2)

    def clean_custom_attributes(self):
        data = self.cleaned_data.get('custom_attributes', '')
        if not data.strip():
            return dict()
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Custom attributes must be a JSON object (dictionary), not a list or other type.")
            return parsed
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {str(e)}")


class PhotoForm(forms.ModelForm, FormWithCustomAttributesFieldMixin):
    albums = forms.ModelMultipleChoiceField(
        queryset=Album.objects.all().order_by('title'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Albums"
    )
    tags = forms.CharField(required=False, widget=forms.HiddenInput())
    slug = forms.CharField(
        required=False,
        help_text="Leave blank to auto calculate"
    )
    canonical_hidden = forms.BooleanField(required=False, initial=False, help_text="Set the default visibility of this photo for publishing channels.")
    canonical_publish_date = forms.DateTimeField(
        required=False,
        help_text="Set the default publish date/time for the photo.",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    location = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

        if self.instance and self.instance.pk:
            # pre-check albums the photo already belongs to
            self.fields['albums'].initial = self.instance.albums.all()

            current_tags = [pt.name for pt in self.instance.tags.all()]
            self.fields['tags'].initial = ";".join(current_tags)
            # Also add a list version for the template
            self.initial['tags_list'] = list(current_tags)

            # Handle location as a simple string like latitude;longitude
            if self.instance.latitude is not None and self.instance.longitude is not None:
                location_value = f"{self.instance.latitude};{self.instance.longitude}"
                self.fields['location'].initial = location_value
                self.initial['location'] = location_value
            else:
                self.fields['location'].initial = ""
                self.initial['location'] = ""

        else:
            # For new photos, set publish_date to now by default
            self.fields['canonical_publish_date'].initial = timezone.now()
            self.fields['canonical_publish_date'].widget.attrs['x-model'] = 'canonicalPublishDate'

    class Meta:
        model = Photo
        fields = ["title", "description", "raw_image", "slug", "canonical_hidden", "hide_location", "canonical_publish_date", "custom_attributes", "albums"]
    
    def save(self, commit=True):
        """
        Save the photo form.
        
        Args:
            commit: Whether to save to database
        """
        # Check if this is a new photo
        is_new = self.instance.pk is None
        
        if not commit:
            # Just return unsaved instance
            return super().save(commit=False)
        
        photo = super().save(commit=True)
        
        if is_new:
            # Schedule the post-creation task (which will trigger signals).
            post_photo_create.delay_on_commit(photo.id)

        # Assign albums with sequential order using a model method
        selected_albums = self.cleaned_data.get('albums', [])
        photo.assign_albums(selected_albums)
        
        # Handle tags
        tags_str = self.cleaned_data.get("tags", "")
        tags_list = [t.strip().lower() for t in tags_str.split(";") if t.strip()]

        # Remove old tag entries not in new list
        photo.tags.exclude(name__in=tags_list).delete()

        # Add new tags (create Tag if necessary)
        for tag_name in tags_list:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            PhotoTag.objects.get_or_create(photo=photo, tag=tag)
        
        # Handle location
        location_str = self.cleaned_data.get("location", "")
        if location_str:
            try:
                lat_str, lon_str = location_str.split(";")
                photo.latitude = float(lat_str.strip())
                photo.longitude = float(lon_str.strip())
                photo.save()
            except ValueError:
                # Invalid format, ignore or handle as needed
                pass
        else:
            # If location field is empty, clear existing location data
            if photo.latitude is not None or photo.longitude is not None:
                photo.latitude = None
                photo.longitude = None
                photo.save()
        
        # clean up orphaned tags
        Tag.objects.filter(photos__isnull=True).delete()


        return photo


class PhotoChannelForm(forms.Form):
    """Configure the channels a photo should be published to."""

    def __init__(self, *args, photo_instance=None, canonical_publish_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.photo_instance = photo_instance
        self.channels = list(Channel.objects.all().order_by('name'))
        existing = {}
        if photo_instance and photo_instance.pk:
            existing = {
                channel_photo.channel_id: channel_photo
                for channel_photo in ChannelPhoto.objects.filter(photo=photo_instance)
            }

        default_date = canonical_publish_date or getattr(
            photo_instance, 'canonical_publish_date', None
        ) or timezone.now()
        self.channel_rows = []
        for channel in self.channels:
            channel_photo = existing.get(channel.pk)
            publish_name = self.publish_field_name(channel)
            date_name = self.date_field_name(channel)
            self.fields[publish_name] = forms.BooleanField(
                required=False,
                label='',
                initial=(
                    bool(channel_photo)
                    if photo_instance and photo_instance.pk
                    else channel.include_new_photos
                ),
                widget=forms.CheckboxInput(attrs={'data-channel-publish': ''}),
            )
            self.fields[date_name] = forms.DateTimeField(
                required=False,
                label='',
                initial=channel_photo.publish_date if channel_photo else default_date,
                widget=forms.DateTimeInput(
                    attrs={'type': 'datetime-local', 'data-channel-publish-date': ''},
                    format='%Y-%m-%dT%H:%M',
                ),
                input_formats=['%Y-%m-%dT%H:%M'],
            )
            self.channel_rows.append((channel, self[publish_name], self[date_name]))

    @staticmethod
    def publish_field_name(channel):
        return f'channel_{channel.pk}_publish'

    @staticmethod
    def date_field_name(channel):
        return f'channel_{channel.pk}_publish_date'

    def clean(self):
        cleaned_data = super().clean()
        for channel in self.channels:
            if (
                cleaned_data.get(self.publish_field_name(channel))
                and not cleaned_data.get(self.date_field_name(channel))
            ):
                self.add_error(
                    self.date_field_name(channel),
                    'A publish date is required when publishing to a channel.',
                )
        return cleaned_data

    def save(self, photo):
        """Create, update, or remove each selected channel-photo relationship."""
        for channel in self.channels:
            channel_photos = ChannelPhoto.objects.filter(channel=channel, photo=photo)
            channel_photo = channel_photos.first()
            if not self.cleaned_data[self.publish_field_name(channel)]:
                if channel_photo is not None:
                    channel_photo.delete()
                continue

            publish_date = self.cleaned_data[self.date_field_name(channel)]
            if channel_photo is None:
                ChannelPhoto.objects.create(
                    channel=channel,
                    photo=photo,
                    publish_date=publish_date,
                )
            else:
                channel_photo.publish_date = publish_date
                channel_photo.save(update_fields=['publish_date'])
                channel_photos.exclude(pk=channel_photo.pk).delete()


class SizeForm(forms.ModelForm):
    class Meta:
        model = Size
        fields = ["slug", "comment", "max_dimension", "square_crop", "public"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

        # If we're editing an existing instance and it's builtin
        if self.instance and getattr(self.instance, "builtin", False):
            self.fields["slug"].disabled = True
            self.fields["comment"].disabled = True


class AlbumForm(forms.ModelForm, FormWithCustomAttributesFieldMixin):
    slug = forms.CharField(
        required=False,
        help_text="Leave blank to auto calculate"
    )
    parent = forms.ModelChoiceField(
        queryset=Album.objects.none(),
        required=False,
        label="Parent Album"
    )
    sort_descending = forms.BooleanField(
        required=False,
        help_text="This is ignored by manual and random sort modes."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # Exclude current album from parent choices
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Album.objects.exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = Album.objects.all()

    class Meta:
        model = Album
        exclude = ["_photos", "children"]


class TagForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = Tag
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter tag name"})
        }


class ChannelForm(forms.ModelForm):

    class Meta:
        model = Channel
        fields = ["name", "description", "include_new_photos"]


class ChannelPublicationHelperForm(forms.Form):
    """Scheduling and conflict choices for the channel publication helper."""

    WEEKDAY_CHOICES = (
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    )
    CONFLICT_CHOICES = (
        ("skip", "Ignore the existing publication"),
        ("recreate", "Delete and recreate it with the new date"),
    )

    channel = forms.ModelChoiceField(
        queryset=Channel.objects.all().order_by("name"),
        empty_label=None,
    )
    start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "x-model": "startDateTime",
                "@change": "if (!endDateTime || endDateTime < startDateTime) endDateTime = startDateTime",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    end_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "x-model": "endDateTime",
                "x-bind:min": "startDateTime",
                "@change": "if (endDateTime < startDateTime) endDateTime = startDateTime",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    weekdays = forms.TypedMultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        coerce=int,
        initial=tuple(range(7)),
        widget=forms.CheckboxSelectMultiple,
        label="Days of week",
    )
    time_start = forms.TimeField(
        initial=time(0, 0),
        widget=forms.TimeInput(
            attrs={"type": "time", "x-model": "timeStart"},
            format="%H:%M",
        ),
        input_formats=["%H:%M"],
        label="Earliest time",
    )
    time_end = forms.TimeField(
        initial=time(23, 59),
        widget=forms.TimeInput(
            attrs={"type": "time", "x-model": "timeEnd"},
            format="%H:%M",
        ),
        input_formats=["%H:%M"],
        label="Latest time",
    )
    jitter = forms.IntegerField(
        min_value=0,
        initial=0,
        label="Jitter (minutes)",
        help_text="Each calculated time is shifted randomly by up to this many minutes.",
    )
    respect_default_channel = forms.BooleanField(
        required=False,
        initial=False,
        label="Respect Default Channel",
        help_text=(
            "For photos not yet published in the default channel, copy that "
            "channel's publication date instead of applying this schedule."
        ),
        widget=forms.CheckboxInput(attrs={"x-model": "respectDefaultChannel"}),
    )
    conflict_resolution = forms.ChoiceField(
        choices=CONFLICT_CHOICES,
        initial="skip",
        widget=forms.RadioSelect,
        label="Existing publication",
    )
    filter_query = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, channel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            now = timezone.localtime().replace(second=0, microsecond=0)
            self.initial.setdefault("start_datetime", now)
            self.initial.setdefault("end_datetime", now)
            if channel is not None:
                self.initial.setdefault("channel", channel)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_datetime")
        end = cleaned_data.get("end_datetime")
        if start and end and end < start:
            self.add_error("end_datetime", "End datetime must be greater than or equal to start datetime.")

        day_start = cleaned_data.get("time_start")
        day_end = cleaned_data.get("time_end")
        if day_start and day_end and day_end <= day_start:
            self.add_error("time_end", "Latest time must be later than earliest time.")
        return cleaned_data
