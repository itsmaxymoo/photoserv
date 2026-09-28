import django_tables2 as tables
from django.contrib.auth.models import Group

from .models import *


class UserTable(tables.Table):
    username = tables.Column(linkify=True)

    class Meta:
        model = User
        fields = ("username", "email", "last_login")
        order_by = ("username")


class GroupTable(tables.Table):
    name = tables.Column(
        linkify=("group-detail", {"pk": tables.A("pk")}),
    )

    class Meta:
        model = Group
        fields = ("name",)
        order_by = ("name",)
