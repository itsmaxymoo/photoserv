from django.db import models
import os
import uuid
from django.urls import reverse
from django.utils.text import slugify
from . import CONTENT_BASE_PATH


class Photo(models.Model):
    def get_image_file_path(instance, filename, suffix="_original"):
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:8]
        kebab_title = slugify(instance.title)
        basename = {random_str}-{kebab_title}
        new_filename = f"{basename}/{basename}_{suffix}{ext}"
        return os.path.join(f"{CONTENT_BASE_PATH}/photos/", new_filename)

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=4096)
    raw_image = models.ImageField(upload_to=get_image_file_path)
    publish_date = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse("photo-detail", kwargs={"pk": self.pk})

    def __str__(self):
        return self.title


class PhotoExif(models.Model):
    photo = models.OneToOneField(Photo, on_delete=models.CASCADE, related_name="exif")
    capture_date = models.DateTimeField(default=None, null=True, blank=True)

    def __str__(self):
        return f"EXIF for {str(self.photo)}"


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
            order_by = "photo__exif__capture_date"
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


class Size(models.Model):
    slug = models.CharField(max_length=32, unique=True)
    max_dimension = models.PositiveIntegerField()
    square_crop = models.BooleanField(default=False)
    builtin = models.BooleanField(default=False)

    # Disallow modifying a builtin size
    def save(self, *args, **kwargs):
        if self.builtin and (self.slug or self.max_dimension or self.square_crop):
            raise ValueError("Cannot modify a builtin size.")
        super().save(*args, **kwargs)

    # Disallow deleting a builtin size
    def delete(self, *args, **kwargs):
        if self.builtin:
            raise ValueError("Cannot delete a builtin size.")
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.max_dimension}px)"
    
    class Meta:
        ordering = ["max_dimension"]

    # Form validation
    def clean(self):
        if not self.slug:
            raise ValueError("Slug cannot be empty.")
        if self.slug == "original":
            raise ValueError("Slug 'original' is reserved and cannot be used.")
        if self.max_dimension <= 0:
            raise ValueError("Max dimension must be a positive integer.")
        if not isinstance(self.square_crop, bool):
            raise ValueError("Square crop must be a boolean value.")


class PhotoSize(models.Model):
    def get_image_file_path(instance, filename):
        # instance is a PhotoSize instance here
        suffix = instance.size.slug
        # Call Photo's method with photo instance, filename, and custom suffix
        return instance.photo.get_image_file_path(filename, suffix=suffix)

    photo = models.ForeignKey("core.Photo", on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=get_image_file_path)

    class Meta:
        unique_together = ("photo", "size")

    def __str__(self):
        return f"{self.photo.title} - {self.size.slug}"
