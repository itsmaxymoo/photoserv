import os
import uuid
from django.utils.text import slugify
from . import CONTENT_BASE_PATH


def raw_photo_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    random_str = uuid.uuid4().hex[:8]
    kebab_title = slugify(instance.title)
    new_filename = f"{random_str}-{kebab_title}{ext}"
    return os.path.join(f"{CONTENT_BASE_PATH}/raw_photos/", new_filename)
