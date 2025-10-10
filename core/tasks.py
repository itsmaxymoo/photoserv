from celery import shared_task
from . import models
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from PIL.ExifTags import TAGS as ExifTags
from datetime import datetime
import exiftool
from . import CONTENT_RESIZED_PHOTOS_PATH
from django.conf import settings


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

        try:
            gen_size(photo, size)
        except FileNotFoundError:
            return f"Raw image file for photo id {photo.id} not found."
    
    return f"Sizes generated for photo id {photo.id}."


@shared_task
def generate_photo_sizes_for_size(size_id):
    try:
        size = models.Size.objects.get(id=size_id)
    except models.Size.DoesNotExist:
        return f"Size with id {size_id} does not exist."

    photos = models.Photo.objects.all()
    for photo in photos:
        generate_sizes_for_photo.delay(photo.id)
    
    return f"Size generation tasks queued for size id {size.id}."


@shared_task
def delete_files(files):
    for path in files:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    
    return f"Deleted {len(files)} files."


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


@shared_task
def consistency():
    issues = 0

    # Filesystem
    # --- Build full paths under MEDIA_ROOT ---
    resized_photos_dir = os.path.join(settings.MEDIA_ROOT, CONTENT_RESIZED_PHOTOS_PATH)

    # Ensure directories exist
    os.makedirs(resized_photos_dir, exist_ok=True)

    # Photo Sizes
    # 1. Ensure every photo size's image file exists
    photo_sizes = models.PhotoSize.objects.all()
    for photo_size in photo_sizes:
        if not photo_size.image or not os.path.isfile(photo_size.image.path):
            issues += 1
            photo_size.delete()

    # Photo Objects
    photos = models.Photo.objects.all()
    for photo in photos:
        # 1. Ensure every photo has metadata
        if not hasattr(photo, 'metadata'):
            issues += 1
            generate_photo_metadata.delay(photo.id)

        # 3. Ensure every photo has sizes
        sizes = models.Size.objects.all()
        photo_sizes = models.PhotoSize.objects.filter(photo=photo)
        if photo_sizes.count() < sizes.count():
            issues += 1
            generate_sizes_for_photo.delay(photo.id)

    # Filesystem
    # 1. Delete stray resized photos
    resized_photos = models.PhotoSize.objects.values_list('image', flat=True)
    delete_files_list = []
    for disk_file in os.listdir(resized_photos_dir):
        rel_path = os.path.join(CONTENT_RESIZED_PHOTOS_PATH, disk_file)
        abs_path = os.path.join(resized_photos_dir, disk_file)
        if rel_path not in resized_photos:
            issues += 1
            delete_files_list.append(abs_path)

    if len(delete_files_list) > 0:
        delete_files.delay(delete_files_list)

    return f"Identified and queued fixes for {issues} issues." if issues > 0 else "No issues found."
