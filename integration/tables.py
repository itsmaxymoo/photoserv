import django_tables2 as tables

from .models import IntegrationPlugin, RunResult


class IntegrationRunResultTable(tables.Table):
    """Table for displaying RunResult records."""
    start_timestamp = tables.Column(linkify=True)
    end_timestamp = tables.Column(linkify=True)

    class Meta:
        model = RunResult
        fields = (
            "start_timestamp",
            "end_timestamp",
            "caller",
            "successful",
        )
        order_by = ("-start_timestamp",)


class IntegrationPluginTable(tables.Table):
    module = tables.Column(linkify=True)
    nickname = tables.Column(linkify=True)
    active = tables.BooleanColumn()
    valid = tables.BooleanColumn(accessor="valid", verbose_name="Valid")

    def render_integration(self, record):
        return str(record)

    class Meta:
        model = IntegrationPlugin
        fields = (
            "nickname",
            "module",
            "storage_prefix",
            "channel",
            "valid",
            "active",
            "last_run_timestamp",
        )
        order_by = ("module","nickname")
