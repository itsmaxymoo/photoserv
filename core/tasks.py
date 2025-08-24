from celery import shared_task
from . import models
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from PIL.ExifTags import TAGS as ExifTags
from datetime import datetime
import exiftool


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
def parse_exif_date(date_str):
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

    with exiftool.ExifToolHelper() as et:
        metadata_list = et.get_metadata(temp_file_path)
        if not metadata_list:
            return f"No metadata found for photo id {photo.id}."

        # Roll all dicts into one (later dicts overwrite earlier ones)
        metadata_dict = {}
        for d in metadata_list:
            metadata_dict.update(d)

        metadata, created = models.PhotoMetadata.objects.get_or_create(photo=photo)

        # Extract relevant metadata
        metadata.capture_date = parse_exif_date(metadata_dict.get("EXIF:DateTimeOriginal"))
        metadata.rating = metadata_dict.get("XMP:Rating")

        metadata.camera_make = metadata_dict.get("EXIF:Make")
        metadata.camera_model = metadata_dict.get("EXIF:Model")
        metadata.lens_model = metadata_dict.get("Composite:LensID")

        metadata.focal_length = metadata_dict.get("EXIF:FocalLength")
        metadata.focal_length_35mm = metadata_dict.get("EXIF:FocalLengthIn35mmFormat")
        metadata.aperture = metadata_dict.get("EXIF:FNumber")
        metadata.shutter_speed = metadata_dict.get("EXIF:ExposureTime")
        metadata.iso = metadata_dict.get("EXIF:ISO")
        metadata.exposure_program = metadata_dict.get("EXIF:ExposureProgram")
        metadata.exposure_compensation = metadata_dict.get("EXIF:ExposureCompensation")

        metadata.copyright = metadata_dict.get("EXIF:Copyright")

        metadata.save()

        return f"Metadata generated for photo id {photo.id}."