import django_tables2 as tables
from .models import *

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
