import django_tables2 as tables
from .models import *

# Include CSS Classes: pagination

class PhotoTable(tables.Table):
    id = tables.Column(linkify=True)
    thumbnail = tables.TemplateColumn(
        template_name="core/partials/photo_small_thumbnail.html",
        verbose_name="Thumbnail",
        orderable=False,
    )
    title = tables.Column(linkify=True)
    description = tables.Column()
    publish_date = tables.Column()

    class Meta:
        model = Photo
        fields = ("id", "thumbnail", "title", "description", "publish_date")
        order_by = ("-publish_date",)


class SizeTable(tables.Table):
    slug = tables.Column()
    comment = tables.Column()
    max_dimension = tables.Column()
    square_crop = tables.BooleanColumn()

    edit = tables.TemplateColumn(
        template_name="core/partials/size_table_edit_button.html",
        verbose_name="Edit",
        orderable=False
    )

    delete = tables.TemplateColumn(
        template_name="core/partials/size_table_delete_button.html",
        verbose_name="Delete",
        orderable=False
    )

    class Meta:
        model = Size
        fields = ("slug", "comment", "max_dimension", "square_crop", "private")


class AlbumTable(tables.Table):
    title = tables.Column(linkify=True)

    class Meta:
        model = Album
        fields = ("title", "slug", "short_description")
        order_by = ("title",)


class PhotoListTable(tables.Table):
    class Meta:
        model = Photo
        template_name = "core/partials/photo_table.html"


class TagTable(tables.Table):
    name = tables.Column(linkify=True)
    photo_count = tables.Column(verbose_name="Photos")

    class Meta:
        model = Tag
        fields = ("name", "photo_count")
        order_by = ("name",)