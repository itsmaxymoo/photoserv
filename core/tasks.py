from celery import shared_task
from . import models
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from PIL.ExifTags import TAGS as ExifTags
from datetime import datetime
import exiftool


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

        photo_size = models.PhotoSize(photo=photo, size=size)
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


@shared_task
def generate_sizes_for_photo(photo_id):
    try:
        photo = models.Photo.objects.get(id=photo_id)
    except models.Photo.DoesNotExist:
        return f"Photo with id {photo_id} does not exist."

    sizes = models.Size.objects.all()
    for size in sizes:
        if models.PhotoSize.objects.filter(photo=photo, size=size).exists():
            continue  # Skip if already exists

        gen_size(photo, size)


@shared_task
def generate_photo_sizes_for_size(size_id):
    try:
        size = models.Size.objects.get(id=size_id)
    except models.Size.DoesNotExist:
        return f"Size with id {size_id} does not exist."

    photos = models.Photo.objects.all()
    for photo in photos:
        generate_sizes_for_photo.delay(photo.id)


@shared_task
def delete_files(files):
    for path in files:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@shared_task
def generate_photo_metadata(photo_id):
    try:
        photo = models.Photo.objects.get(id=photo_id)
    except models.Photo.DoesNotExist:
        return f"Photo with id {photo_id} does not exist."
    
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
            f"-{METADATA_EXIF_COPYRIGHT}"
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
        metadata.rating = metadata_dict.get(METADATA_XMP_RATING)

        metadata.camera_make = metadata_dict.get(METADATA_EXIF_MAKE)
        metadata.camera_model = metadata_dict.get(METADATA_EXIF_MODEL)
        metadata.lens_model = metadata_dict.get(METADATA_COMPOSITE_LENS_ID)

        metadata.focal_length = metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH)
        metadata.focal_length_35mm = metadata_dict.get(METADATA_EXIF_FOCAL_LENGTH_35MM)
        metadata.aperture = metadata_dict.get(METADATA_EXIF_APERTURE)
        metadata.shutter_speed = metadata_dict.get(METADATA_EXIF_SHUTTER_SPEED)
        metadata.iso = metadata_dict.get(METADATA_EXIF_ISO)

        metadata.exposure_program = metadata_dict.get(METADATA_EXIF_EXPOSURE_PROGRAM)
        metadata.exposure_compensation = metadata_dict.get(METADATA_EXIF_EXPOSURE_COMPENSATION)
        metadata.flash = metadata_dict.get(METADATA_EXIF_FLASH)

        metadata.copyright = metadata_dict.get(METADATA_EXIF_COPYRIGHT)

        metadata.save()

        return f"Metadata generated for photo id {photo.id}."