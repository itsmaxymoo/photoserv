from itertools import groupby

from django.apps import apps


def _app_name(permission):
    app_label = permission.content_type.app_label
    try:
        return str(apps.get_app_config(app_label).verbose_name)
    except LookupError:
        return app_label.replace("_", " ").title()


def group_permissions_by_app(permissions):
    """Return permissions grouped by app, with both levels alphabetized."""

    ordered = sorted(
        permissions,
        key=lambda permission: (
            _app_name(permission).casefold(),
            permission.content_type.app_label.casefold(),
            permission.name.casefold(),
            permission.codename.casefold(),
        ),
    )
    grouped = []
    for _, app_permissions in groupby(
        ordered,
        key=lambda permission: permission.content_type.app_label,
    ):
        app_permissions = list(app_permissions)
        grouped.append((_app_name(app_permissions[0]), app_permissions))
    return grouped
