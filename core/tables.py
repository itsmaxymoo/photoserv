import django_tables2 as tables
from .models import *

# Include CSS Classes: pagination

class PhotoTable(tables.Table):
    id = tables.Column(linkify=True)
    title = tables.Column(linkify=True)
    description = tables.Column()
    publish_date = tables.Column()

    class Meta:
        model = Photo
        fields = ("id", "title", "description", "publish_date")
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
        fields = ("slug", "comment", "max_dimension", "square_crop")


class AlbumTable(tables.Table):
    title = tables.Column(linkify=True)
    description = tables.Column()

    def render_description(self, value):
        return (value[:117] + '...') if value and len(value) > 120 else value

    class Meta:
        model = Album
        fields = ("title", "description")
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