from django.db import models

# Create your models here.
class SiteHealth:
    def __init__(self, total_photos: int, photos_pending_sizes: int, pending_sizes: int, pending_metadata: int):
        self.total_photos = total_photos
        self.photos_pending_sizes = photos_pending_sizes
        self.pending_sizes = pending_sizes
        self.pending_metadata = pending_metadata
