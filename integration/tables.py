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
        fields = ("request", "active", "last_run_timestamp")
        order_by = ("url",)


class PythonPluginTable(tables.Table):
    plugin = tables.Column(accessor='id', verbose_name="Plugin", linkify=True)
    active = tables.BooleanColumn()
    valid = tables.BooleanColumn(accessor='valid', verbose_name="Valid")

    def render_plugin(self, record):
        return str(record)

    class Meta:
        model = PythonPlugin
        fields = ("plugin", "valid", "active", "last_run_timestamp")
        order_by = ("module",)
