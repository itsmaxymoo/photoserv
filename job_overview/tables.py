import django_tables2 as tables
from django_celery_results.models import TaskResult

class TaskResultTable(tables.Table):
    task_name = tables.Column(verbose_name="Name")
    status = tables.Column(verbose_name="Status")
    date_started = tables.DateTimeColumn(format="Y-m-d H:i:s", verbose_name="Started")
    result = tables.Column(verbose_name="Result", accessor="result")

    class Meta:
        model = TaskResult
        fields = ("id", "task_name", "status", "date_started", "result")
        order_by = ("-id",)
