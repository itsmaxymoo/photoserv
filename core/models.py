from django.db import models
from .utils import raw_photo_upload_path


class Photo(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(max_length=4096)
    raw_image = models.ImageField(upload_to=raw_photo_upload_path)
    publish_date = models.DateTimeField(auto_now=True)


class Album(models.Model):
    class DefaultSortMethod(models.TextChoices):
        CREATED = "CREATED", "Created/Taken"
        PUBLISHED = "PUBLISHED", "Published/Uploaded"
        MANUAL = "MANUAL", "Manual"
        RANDOM = "RANDOM", "Random"

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=4096)
    sort_method = models.CharField(
        max_length=10,
        choices=DefaultSortMethod.choices,
        default=DefaultSortMethod.MANUAL
    )
    sort_ascending = models.BooleanField(default=True)


class PhotoInAlbum(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    order = models.IntegerField()