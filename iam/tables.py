import django_tables2 as tables
from .models import *


class UserTable(tables.Table):
    username = tables.Column(linkify=True)

    class Meta:
        model = User
        fields = ("username", "email", "last_login")
        order_by = ("username")
