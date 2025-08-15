from django.db import models
import os
import uuid
from django.urls import reverse
from django.utils.text import slugify
from . import CONTENT_RAW_PHOTOS_PATH, CONTENT_RESIZED_PHOTOS_PATH
from . import tasks


class Photo(models.Model):
    def get_image_file_path(instance, filename):
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:8]
        kebab_title = slugify(instance.title)
        new_filename = f"{random_str}-{kebab_title}{ext}"
        return os.path.join(CONTENT_RAW_PHOTOS_PATH, new_filename)

    title = models.CharField(max_length=255)
    description = models.TextField(max_length=4096)
    raw_image = models.ImageField(upload_to=get_image_file_path)
    publish_date = models.DateTimeField(auto_now=True)

    def get_absolute_url(self):
        return reverse("photo-detail", kwargs={"pk": self.pk})
    
    # After saving a new photo, trigger the task to generate sizes
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            # Automatically create original PhotoSize
            try:
                original_size = Size.objects.get(slug="original")
            except Size.DoesNotExist:
                original_size = None

            if original_size:
                PhotoSize.objects.get_or_create(
                    photo=self,
                    size=original_size,
                    defaults={'image': self.raw_image}
                )

            # Generate other sizes via Celery task
            tasks.generate_sizes_for_photo.delay_on_commit(self.id)

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

        # Delete all existing PhotoSizes for this size
        PhotoSize.objects.filter(size=self).delete()

        # Trigger task to regenerate photos for this size after DB commit
        tasks.generate_photo_sizes_for_size.delay_on_commit(self.id)

    # Disallow deleting a builtin size
    def delete(self, *args, **kwargs):
        if self.builtin:
            raise ValueError("Cannot delete a builtin size.")
        
        file_paths = list(self.photos.values_list("image", flat=True))
        self.photos.all().delete()

        if file_paths:
            tasks.size_delete_cleanup.delay_on_commit(file_paths)

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
        ext = os.path.splitext(filename)[1]
        random_str = uuid.uuid4().hex[:16]
        kebab_title = slugify(instance.photo.title)
        new_filename = f"{random_str}-{kebab_title}_{instance.size.slug}{ext}"
        return os.path.join(CONTENT_RESIZED_PHOTOS_PATH, new_filename)

    photo = models.ForeignKey("core.Photo", on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey(Size, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=get_image_file_path)

    class Meta:
        unique_together = ("photo", "size")

    def __str__(self):
        return f"{self.photo.title} - {self.size.slug}"
