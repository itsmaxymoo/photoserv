class CRUDGenericMixin:
    object_type_name = "Object"
    object_type_name_plural = None
    object_url_name_slug = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_type_name"] = self.object_type_name
        context["object_type_name_plural"] = self.object_type_name_plural or f"{self.object_type_name}s"
        context["object_url_name_slug"] = self.object_url_name_slug or self.object_type_name.lower()

        return context
