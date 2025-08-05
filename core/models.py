from django.db import models
import os
import uuid
from django.urls import reverse
from django.utils.text import slugify
from . import CONTENT_BASE_PATH


class Photo(models.Model):
    def get_raw_photo_upload_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:8]
        kebab_title = slugify(instance.title)
        new_filename = f"{random_str}-{kebab_title}_original{ext}"
        return os.path.join(f"{CONTENT_BASE_PATH}/photos/", new_filename)

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=4096)
    raw_image = models.ImageField(upload_to=get_raw_photo_upload_path)
    publish_date = models.DateTimeField(auto_now=True)

    capture_date = models.DateTimeField(default=None, null=True, blank=True)

    def get_absolute_url(self):
        return reverse("photo-detail", kwargs={"pk": self.pk})

    def __str__(self):
        return self.title


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
    _photos = models.ManyToManyField(
        "Photo",
        through="PhotoInAlbum",
        related_name="albums"
    )

    def get_ordered_photos(self):
        qs = self.photos.all()

        if self.sort_method == self.DefaultSortMethod.MANUAL:
            order_by = "photoinalbum__order"
        elif self.sort_method == self.DefaultSortMethod.CREATED:
            order_by = "photo__publish_date"
        elif self.sort_method == self.DefaultSortMethod.PUBLISHED:
            order_by = "photo__publish_date"
        elif self.sort_method == self.DefaultSortMethod.RANDOM:
            return qs.order_by("?")  # random order, no need for sort_ascending
        else:
            order_by = "photoinalbum__order"

        if not self.sort_ascending:
            order_by = f'-{order_by}'

        return qs.order_by(order_by)

    def __str__(self):
        return self.title


class PhotoInAlbum(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        unique_together = ("album", "photo")
        ordering = ["order"]
    
    def __str__(self):
        return f"{self.album.title} -> {self.photo.title}"
