from . import models
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from PIL.ExifTags import TAGS as ExifTags
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import random
import exiftool
import hashlib


# Metadata tag constants
METADATA_EXIF_DATETIME_ORIGINAL = "EXIF:DateTimeOriginal"
METADATA_XMP_RATING = "XMP:Rating"

METADATA_EXIF_MAKE = "EXIF:Make"
METADATA_EXIF_MODEL = "EXIF:Model"
METADATA_COMPOSITE_LENS_ID = "Composite:LensID"

METADATA_EXIF_FOCAL_LENGTH = "EXIF:FocalLength"
METADATA_EXIF_FOCAL_LENGTH_35MM = "Composite:FocalLength35efl"
METADATA_EXIF_APERTURE = "EXIF:FNumber"
METADATA_EXIF_SHUTTER_SPEED = "EXIF:ExposureTime"
METADATA_EXIF_ISO = "EXIF:ISO"

METADATA_EXIF_EXPOSURE_PROGRAM = "EXIF:ExposureProgram"
METADATA_EXIF_EXPOSURE_COMPENSATION = "EXIF:ExposureCompensation"
METADATA_EXIF_FLASH = "EXIF:Flash"

METADATA_EXIF_COPYRIGHT = "EXIF:Copyright"

METADATA_COMPOSITE_LATITUDE = "Composite:GPSLatitude"
METADATA_COMPOSITE_LONGITUDE = "Composite:GPSLongitude"


@dataclass(frozen=True)
class PublicationRates:
    """Average publication rates for a constrained weekly schedule."""

    per_day: float
    per_week: float
    per_month: float
    eligible_days: int


def publication_windows(start, end, weekdays, day_start, day_end):
    """Return allowed datetime intervals within an inclusive datetime range.

    ``weekdays`` uses Python's weekday numbering (Monday is 0). Time-of-day
    intervals must be increasing; overnight intervals are intentionally not
    inferred so invalid configuration is caught by the form.
    """
    if end < start:
        raise ValueError("End datetime must be greater than or equal to start datetime.")
    if day_end <= day_start:
        raise ValueError("End time must be later than start time.")

    weekdays = {int(day) for day in weekdays}
    if not weekdays or not weekdays.issubset(set(range(7))):
        raise ValueError("At least one valid weekday is required.")

    tzinfo = start.tzinfo
    windows = []
    current_date = start.date()
    while current_date <= end.date():
        if current_date.weekday() in weekdays:
            window_start = datetime.combine(current_date, day_start, tzinfo=tzinfo)
            window_end = datetime.combine(current_date, day_end, tzinfo=tzinfo)
            clipped_start = max(start, window_start)
            clipped_end = min(end, window_end)
            if clipped_start <= clipped_end:
                windows.append((clipped_start, clipped_end))
        current_date += timedelta(days=1)
    return windows


def calculate_publication_schedule(
    photo_count,
    start,
    end,
    weekdays,
    day_start=time.min,
    day_end=time(23, 59),
    jitter_minutes=0,
    rng=None,
):
    """Evenly distribute publication datetimes across allowed windows.

    Jitter is applied after the constrained times are calculated, as an
    independent whole-minute offset in the inclusive range ``[-jitter,
    jitter]``. Pass a random-compatible object for deterministic callers.
    """
    if photo_count < 0:
        raise ValueError("Photo count cannot be negative.")
    if jitter_minutes < 0:
        raise ValueError("Jitter cannot be negative.")
    if photo_count == 0:
        return []

    windows = publication_windows(start, end, weekdays, day_start, day_end)
    if not windows:
        raise ValueError("The selected date range contains no eligible publication times.")

    durations = [(window_end - window_start).total_seconds() for window_start, window_end in windows]
    total_seconds = sum(durations)
    if photo_count == 1 or total_seconds == 0:
        offsets = [0.0] * photo_count
    else:
        spacing = total_seconds / (photo_count - 1)
        offsets = [spacing * index for index in range(photo_count)]

    schedule = []
    for offset in offsets:
        remaining = offset
        calculated = windows[-1][1]
        for (window_start, window_end), duration in zip(windows, durations):
            if remaining <= duration:
                calculated = window_start + timedelta(seconds=remaining)
                break
            remaining -= duration
        schedule.append(calculated)

    jitter_minutes = int(jitter_minutes)
    if jitter_minutes:
        rng = rng or random
        schedule = [
            publish_date + timedelta(minutes=rng.randint(-jitter_minutes, jitter_minutes))
            for publish_date in schedule
        ]
    return schedule


def calculate_publication_rates(photo_count, start, end, weekdays):
    """Calculate rates without counting unselected weekdays as active days."""
    weekdays = {int(day) for day in weekdays}
    if not weekdays or not weekdays.issubset(set(range(7))):
        raise ValueError("At least one valid weekday is required.")
    if end < start:
        raise ValueError("End datetime must be greater than or equal to start datetime.")

    eligible_days = 0
    current_date = start.date()
    while current_date <= end.date():
        if current_date.weekday() in weekdays:
            eligible_days += 1
        current_date += timedelta(days=1)

    per_day = photo_count / eligible_days if eligible_days else 0.0
    per_week = per_day * len(weekdays)
    return PublicationRates(
        per_day=per_day,
        per_week=per_week,
        per_month=per_week * 52 / 12,
        eligible_days=eligible_days,
    )


def gen_size(photo, size):
    photo.raw_image.open()  # ensure file is ready
    with Image.open(photo.raw_image) as img:
        exif_data = img.info.get('exif') # Preserve EXIF data

        # Use updated resampling constant
        img.thumbnail((size.max_dimension, size.max_dimension), Image.Resampling.LANCZOS)

        # Square crop, centered
        if size.square_crop:
            width, height = img.size
            min_dim = min(width, height)
            left = (width - min_dim) // 2
            top = (height - min_dim) // 2
            right = left + min_dim
            bottom = top + min_dim
            img = img.crop((left, top, right, bottom))
            # Resize to exact max_dimension if necessary
            if min_dim != size.max_dimension:
                img = img.resize((size.max_dimension, size.max_dimension), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        if exif_data:
            img.save(buffer, format='JPEG', exif=exif_data)
        else:
            img.save(buffer, format='JPEG')

        photo_size = models.PhotoSize(photo=photo, size=size, height=img.height, width=img.width, md5=hashlib.md5(buffer.getvalue()).hexdigest())
        photo_size.image.save(
            f"{photo.id}_{size.slug}.jpg",
            ContentFile(buffer.getvalue()),
            save=True
        )

        return f"Sizes generated for photo id {photo.id}."


# Function parse_exif_date. Returns datetime object or None
def parse_exif_date(date_str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def parse_numeric(value, cast=float):
    """Convert a value to a numeric type, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return cast(value)
    except (ValueError, TypeError):
        return None


def generate_metadata_for_photo(photo: "models.Photo"):
    photo.raw_image.open()  # ensure file is ready
    temp_file_path = photo.raw_image.path

    with exiftool.ExifToolHelper(common_args=["-G"]) as et:
        metadata_list = et.get_metadata(temp_file_path, [
            f"-{METADATA_EXIF_DATETIME_ORIGINAL}",
            f"-{METADATA_XMP_RATING}",
            f"-{METADATA_EXIF_MAKE}",
            f"-{METADATA_EXIF_MODEL}",
            f"-{METADATA_COMPOSITE_LENS_ID}",
            f"-{METADATA_EXIF_FOCAL_LENGTH}#",
            f"-{METADATA_EXIF_FOCAL_LENGTH_35MM}#",
            f"-{METADATA_EXIF_APERTURE}#",
            f"-{METADATA_EXIF_SHUTTER_SPEED}#",
            f"-{METADATA_EXIF_ISO}#",
            f"-{METADATA_EXIF_EXPOSURE_PROGRAM}",
            f"-{METADATA_EXIF_EXPOSURE_COMPENSATION}#",
            f"-{METADATA_EXIF_FLASH}",
            f"-{METADATA_EXIF_COPYRIGHT}",
            f"-{METADATA_COMPOSITE_LATITUDE}#",
            f"-{METADATA_COMPOSITE_LONGITUDE}#",
        ])
        if not metadata_list:
            return f"No metadata found for photo id {photo.id}."

        # Roll all dicts into one (later dicts overwrite earlier ones)
        metadata_dict = {}
        for d in metadata_list:
            metadata_dict.update(d)

        metadata, created = models.PhotoMetadata.objects.get_or_create(photo=photo)

        # Extract relevant metadata
        metadata.capture_date = parse_exif_date(metadata_dict.get(METADATA_EXIF_DATETIME_ORIGINAL))
        metadata.rating = parse_numeric(metadata_dict.get(METADATA_XMP_RATING), cast=int)

        metadata.camera_make = metadata_dict.get(METADATA_EXIF_MAKE)
        metadata.camera_model = metadata_dict.get(METADATA_EXIF_MODEL)
        metadata.lens_model = metadata_dict.get(METADATA_COMPOSITE_LENS_ID)

        metadata.focal_length = parse_numeric(metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH))
        metadata.focal_length_35mm = parse_numeric(metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH_35MM))
        metadata.aperture = parse_numeric(metadata_dict.get(METADATA_EXIF_APERTURE))
        metadata.shutter_speed = parse_numeric(metadata_dict.get(METADATA_EXIF_SHUTTER_SPEED))
        metadata.iso = parse_numeric(metadata_dict.get(METADATA_EXIF_ISO), cast=int)

        metadata.exposure_program = metadata_dict.get(METADATA_EXIF_EXPOSURE_PROGRAM)
        metadata.exposure_compensation = parse_numeric(metadata_dict.get(METADATA_EXIF_EXPOSURE_COMPENSATION))
        metadata.flash = metadata_dict.get(METADATA_EXIF_FLASH)

        metadata.copyright = metadata_dict.get(METADATA_EXIF_COPYRIGHT)

        metadata.raw_latitude = parse_numeric(metadata_dict.get(METADATA_COMPOSITE_LATITUDE))
        metadata.raw_longitude = parse_numeric(metadata_dict.get(METADATA_COMPOSITE_LONGITUDE))

        metadata.save()

        # If the photo's lat/long is null, update it from metadata
        if photo.latitude is None or photo.longitude is None:
            if metadata.raw_latitude is not None and metadata.raw_longitude is not None:
                photo.latitude = metadata.raw_latitude
                photo.longitude = metadata.raw_longitude
                photo.save(update_fields=['latitude', 'longitude'])


def publish_photos() -> int:
    chg = 0
    for channel_photo in models.ChannelPhoto.objects.all():
        if channel_photo.update_published():
            chg += 1
        channel_photo.save()

    return chg
