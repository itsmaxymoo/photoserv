class CRUDGenericMixin:
    object_type_name = "Object"
    object_type_name_plural = None
    object_url_name_slug = None
    no_object_detail_page = False
    can_directly_create = True
    can_edit = True

    edit_disclaimer = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_type_name"] = self.object_type_name
        context["object_type_name_plural"] = self.object_type_name_plural or f"{self.object_type_name}s"
        context["object_url_name_slug"] = self.object_url_name_slug or self.object_type_name.lower()
        context["no_object_detail_page"] = self.no_object_detail_page == True if hasattr(self, 'no_object_detail_page') else False
        context["edit_disclaimer"] = self.edit_disclaimer
        context["can_directly_create"] = self.can_directly_create
        context["can_edit"] = self.can_edit if hasattr(self, 'can_edit') else True
        context["formset_support"] = self.formset_support if hasattr(self, 'formset_support') else False

        return context
