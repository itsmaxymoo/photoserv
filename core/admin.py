from django.contrib import admin

# Register your models here.
from .models import Photo, Album, PhotoInAlbum

admin.site.register([Photo, Album, PhotoInAlbum])