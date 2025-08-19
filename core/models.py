from django.db import models
import os
import uuid
from django.urls import reverse
from django.utils.text import slugify
from . import CONTENT_RAW_PHOTOS_PATH, CONTENT_RESIZED_PHOTOS_PATH
from . import tasks
from django.core.exceptions import ValidationError


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

    def get_size(self, size: str):
        return self.sizes.filter(size__slug=size).first()
    
    # After saving a new photo, trigger the task to generate sizes
    def save(self, *args, **kwargs):
        is_new = self.pk is None

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
    
    def assign_albums(self, albums):
        # Remove unselected
        PhotoInAlbum.objects.filter(photo=self).exclude(album__in=albums).delete()

        for album in albums:
            if not PhotoInAlbum.objects.filter(photo=self, album=album).exists():
                last_order = (
                    PhotoInAlbum.objects.filter(album=album)
                    .aggregate(max_order=models.Max('order'))['max_order']
                )
                next_order = (last_order or 0) + 1
                PhotoInAlbum.objects.create(photo=self, album=album, order=next_order)

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

    title = models.CharField(max_length=255, unique=True)
    description = models.TextField(max_length=4096)
    sort_method = models.CharField(
        max_length=10,
        choices=DefaultSortMethod.choices,
        default=DefaultSortMethod.PUBLISHED
    )
    sort_descending = models.BooleanField(default=False)
    _photos = models.ManyToManyField(
        "Photo",
        through="PhotoInAlbum",
        related_name="albums",
        verbose_name="Photos"
    )

    def get_ordered_photos(self):
        qs = self._photos.all()

        if self.sort_method == self.DefaultSortMethod.MANUAL:
            order_by = "photoinalbum__order"
        elif self.sort_method == self.DefaultSortMethod.CREATED:
            order_by = "exif__capture_date"
        elif self.sort_method == self.DefaultSortMethod.PUBLISHED:
            order_by = "publish_date"
        elif self.sort_method == self.DefaultSortMethod.RANDOM:
            return qs.order_by("?")  # random order, no need for sort_ascending
        else:
            order_by = "photoinalbum__order"

        if self.sort_descending:
            order_by = f'-{order_by}'

        return qs.order_by(order_by)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse("album-detail", kwargs={"pk": self.pk})


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
    comment = models.CharField(max_length=255, blank=True, null=True)
    max_dimension = models.PositiveIntegerField()
    square_crop = models.BooleanField(default=False)
    builtin = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=True)

    def clean(self):
        # Prevent modifications to builtin sizes
        if not self.can_edit:
            raise ValidationError("Cannot modify this size.")
        # Don't allow changes to slug or comment if it's a builtin size
        orig = Size.objects.get(pk=self.pk)
        if self.builtin and (self.slug != orig.slug or self.comment != orig.comment):
            raise ValidationError("Cannot change the slug or comment of a builtin size.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        file_paths = list(self.photos.values_list("image", flat=True))
        self.photos.all().delete()

        if file_paths:
            tasks.size_delete_cleanup.delay_on_commit(file_paths)

        # Trigger task to regenerate photos for this size after DB commit
        tasks.generate_photo_sizes_for_size.delay_on_commit(self.id)

    # Disallow deleting a builtin size
    def delete(self, *args, **kwargs):
        if self.builtin or not self.can_edit:
            raise ValidationError("Cannot delete a builtin size.")
        
        file_paths = list(self.photos.values_list("image", flat=True))
        self.photos.all().delete()

        if file_paths:
            tasks.size_delete_cleanup.delay_on_commit(file_paths)

        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.slug} ({self.max_dimension}px)"
    
    class Meta:
        ordering = ["max_dimension"]


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
