import django_tables2 as tables
from .models import *

class WebRequestTable(tables.Table):
    request = tables.Column(accessor='id', verbose_name="Request", linkify=True)
    active = tables.BooleanColumn()

    def render_request(self, record):
        return str(record)

    class Meta:
        model = WebRequest
        fields = ("request", "active")
        order_by = ("url",)
