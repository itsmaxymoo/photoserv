import django_tables2 as tables
from .models import *

class PhotoTable(tables.Table):
    id = tables.Column(linkify=True)
    title = tables.Column(linkify=True)
    description = tables.Column()
    date_taken = tables.Column()

    class Meta:
        model = Photo
        fields = ("id", "title", "description", "publish_date")
