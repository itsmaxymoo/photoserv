import uuid

import django_filters
from django import forms
from django_filters.constants import EMPTY_VALUES
from django_filters.widgets import RangeWidget
from rest_framework.exceptions import ValidationError as DRFValidationError

from .api_access import get_public_entity, has_internal_identifier_access
from .models import Album, Channel, ChannelPhoto, Photo, PhotoMetadata, Tag
from .widgets import *
from .fields import *


class PublicEntityIdentifierFilter(django_filters.CharFilter):
    """Filter a relationship by UUID, or by ID for trusted requests."""

    def __init__(self, *args, entity_model, **kwargs):
        self.entity_model = entity_model
        super().__init__(*args, **kwargs)

    def filter(self, queryset, value):
        if value in EMPTY_VALUES:
            return queryset
        request = getattr(self.parent, "request", None)
        try:
            entity = get_public_entity(
                self.entity_model._default_manager.all(),
                value,
                request,
            )
        except self.entity_model.DoesNotExist:
            try:
                valid_uuid = uuid.UUID(str(value))
            except (AttributeError, TypeError, ValueError):
                valid_uuid = None
            try:
                valid_id = int(value)
            except (TypeError, ValueError):
                valid_id = None
            if valid_uuid is not None or (
                has_internal_identifier_access(request)
                and valid_id is not None
                and valid_id > 0
            ):
                return queryset.none()
            raise DRFValidationError(
                {self.field_name: "Enter a valid UUID or permitted database ID."}
            )

        pk_field_name = self.field_name.removesuffix("uuid") + "pk"
        lookup = "__".join([pk_field_name, self.lookup_expr])
        queryset = queryset.filter(**{lookup: entity.pk})
        return queryset.distinct() if self.distinct else queryset


class ShutterSpeedRangeFilter(django_filters.RangeFilter):
    """
    Custom RangeFilter for shutter speed that uses ShutterSpeedRangeField 
    to accept both decimal and fractional notation.
    """
    field_class = ShutterSpeedRangeField


class PhotoFilter(django_filters.FilterSet):
    """
    Comprehensive filter for Photo model including metadata fields.
    Supports filtering by title, slug, description, publish date, metadata fields,
    albums, and tags.
    """
    
    # Basic Photo fields - case-insensitive search
    title = django_filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        label='Title'
    )
    
    slug = django_filters.CharFilter(
        field_name='slug',
        lookup_expr='icontains',
        label='Slug'
    )
    
    description = django_filters.CharFilter(
        field_name='description',
        lookup_expr='icontains',
        label='Description'
    )
    
    # Publish date filters
    canonical_publish_date = django_filters.DateFromToRangeFilter(
        field_name='canonical_publish_date',
        label='Canonical Publish date',
        widget=CrispyDateRangeWidget()
    )
    
    # Album and Tag filters (many-to-many)
    albums = django_filters.ModelMultipleChoiceFilter(
        field_name='albums',
        queryset=Album.objects.all(),
        label='Albums',
        widget=forms.CheckboxSelectMultiple
    )
    
    tags = django_filters.ModelMultipleChoiceFilter(
        field_name='tags',
        queryset=Tag.objects.all(),
        label='Tags',
        widget=forms.CheckboxSelectMultiple
    )
    
    # PhotoMetadata fields - Datetime
    capture_date = django_filters.DateTimeFromToRangeFilter(
        field_name='metadata__capture_date',
        label='Capture date',
        widget=CrispyDateRangeWidget()
    )
    
    # PhotoMetadata fields - Numeric (rating)
    rating = django_filters.RangeFilter(
        field_name='metadata__rating',
        label='Rating',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '1'})
    )
    
    # PhotoMetadata fields - CharFields with case-insensitive search
    camera_make = django_filters.CharFilter(
        field_name='metadata__camera_make',
        lookup_expr='icontains',
        label='Camera make'
    )
    
    camera_model = django_filters.CharFilter(
        field_name='metadata__camera_model',
        lookup_expr='icontains',
        label='Camera model'
    )
    
    lens_model = django_filters.CharFilter(
        field_name='metadata__lens_model',
        lookup_expr='icontains',
        label='Lens model'
    )
    
    exposure_program = django_filters.CharFilter(
        field_name='metadata__exposure_program',
        lookup_expr='icontains',
        label='Exposure program (PASM)'
    )
    
    flash = django_filters.CharFilter(
        field_name='metadata__flash',
        lookup_expr='icontains',
        label='Flash'
    )
    
    copyright = django_filters.CharFilter(
        field_name='metadata__copyright',
        lookup_expr='icontains',
        label='Copyright'
    )
    
    # PhotoMetadata fields - Numeric (focal_length)
    focal_length = django_filters.RangeFilter(
        field_name='metadata__focal_length',
        label='Focal length (real)',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (focal_length_35mm)
    focal_length_35mm = django_filters.RangeFilter(
        field_name='metadata__focal_length_35mm',
        label='Focal length (35mm equiv.)',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (aperture)
    aperture = django_filters.RangeFilter(
        field_name='metadata__aperture',
        label='Aperture',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )
    
    # PhotoMetadata fields - Numeric (shutter_speed)
    shutter_speed = ShutterSpeedRangeFilter(
        field_name='metadata__shutter_speed',
        label='Shutter speed',
        widget=CrispyShutterSpeedRangeWidget()
    )
    
    # PhotoMetadata fields - Numeric (iso)
    iso = django_filters.RangeFilter(
        field_name='metadata__iso',
        label='ISO',
        widget=CrispyRangeWidget(attrs={'type': 'number'})
    )
    
    # PhotoMetadata fields - Numeric (exposure_compensation)
    exposure_compensation = django_filters.RangeFilter(
        field_name='metadata__exposure_compensation',
        label='Exposure compensation',
        widget=CrispyRangeWidget(attrs={'type': 'number', 'step': '0.1'})
    )

    # Location filters
    hide_location = django_filters.BooleanFilter(
        field_name='hide_location',
        label='Location hidden',
    )

    has_location_data = django_filters.BooleanFilter(
        label='Has location data',
        method='filter_has_location_data',
    )

    def filter_has_location_data(self, queryset, name, value):
        if value is True:
            return queryset.filter(latitude__isnull=False, longitude__isnull=False)
        elif value is False:
            return queryset.filter(latitude__isnull=True, longitude__isnull=True)
        return queryset

    class Meta:
        model = Photo
        fields = []  # We define all fields explicitly above


class AlbumFilter(django_filters.FilterSet):
    """Filters shared by the HTML UI and the media API."""

    title = django_filters.CharFilter(lookup_expr="icontains")
    slug = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    parent = PublicEntityIdentifierFilter(
        field_name="parent__uuid",
        entity_model=Album,
    )
    photos = PublicEntityIdentifierFilter(
        field_name="_photos__uuid",
        entity_model=Photo,
        distinct=True,
    )

    class Meta:
        model = Album
        fields = ["sort_method", "sort_descending"]


class TagFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    photos = PublicEntityIdentifierFilter(
        field_name="photos__uuid",
        entity_model=Photo,
        distinct=True,
    )

    class Meta:
        model = Tag
        fields = []


class ChannelFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    photos = PublicEntityIdentifierFilter(
        field_name="photos__photo__uuid",
        entity_model=Photo,
        distinct=True,
    )

    class Meta:
        model = Channel
        fields = ["include_new_photos", "builtin"]


class ChannelPhotoFilter(django_filters.FilterSet):
    """Filter channel-membership headers without exposing their database IDs."""

    channel = PublicEntityIdentifierFilter(
        field_name="channel__uuid",
        entity_model=Channel,
    )
    photo = PublicEntityIdentifierFilter(
        field_name="photo__uuid",
        entity_model=Photo,
    )
    publish_date = django_filters.DateTimeFromToRangeFilter()

    class Meta:
        model = ChannelPhoto
        fields = ["published"]


class PhotoAPIFilter(PhotoFilter):
    """PhotoFilter variant whose relationships accept public UUIDs."""

    albums = PublicEntityIdentifierFilter(
        field_name="albums__uuid",
        entity_model=Album,
        distinct=True,
    )
    tags = PublicEntityIdentifierFilter(
        field_name="tags__uuid",
        entity_model=Tag,
        distinct=True,
    )
    channels = PublicEntityIdentifierFilter(
        field_name="channels__channel__uuid",
        entity_model=Channel,
        distinct=True,
    )
    published = django_filters.BooleanFilter(field_name="channels__published")
    include_unpublished = django_filters.BooleanFilter(
        method="filter_include_unpublished"
    )

    def filter_include_unpublished(self, queryset, name, value):
        # Visibility is applied by PhotoViewSet before the regular filters.
        return queryset
