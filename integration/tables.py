import django_tables2 as tables
from .models import *


class IntegrationRunResultTable(tables.Table):
    """Table for displaying IntegrationRunResult records."""
    start_timestamp = tables.Column(linkify=True)
    end_timestamp = tables.Column(linkify=True)

    class Meta:
        model = IntegrationRunResult
        fields = (
            "start_timestamp",
            "end_timestamp",
            "caller",
            "successful",
        )
        order_by = ("-start_timestamp",)


class WebRequestTable(tables.Table):
    request = tables.Column(accessor='id', verbose_name="Request", linkify=True)
    active = tables.BooleanColumn()

    def render_request(self, record):
        return str(record)

    class Meta:
        model = WebRequest
        fields = ("request", "active")
        order_by = ("url",)
