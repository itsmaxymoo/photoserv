from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView
from django_tables2.views import SingleTableView
from .models import *
from .forms import *
from .tables import *
from core.mixins import CRUDGenericMixin
from django_tables2 import RequestConfig


def redirect_to_home(request):
    return redirect(reverse('integration-list'))


#region RunResult

class RunResultMixin(CRUDGenericMixin):
    object_type_name = "Integration Run Result"
    object_url_name_slug = "integration-run-result"
    edit_disclaimer = "These are deleted automatically after a while."
    can_directly_create = False
    can_edit = False


class RunResultListView(RunResultMixin, SingleTableView):
    model = IntegrationRunResult
    table_class = IntegrationRunResultTable
    template_name = "generic_crud_list.html"


class RunResultDetailView(RunResultMixin, DetailView):
    model = IntegrationRunResult
    template_name = "integration/integration_run_result_detail.html"


class RunResultDeleteView(RunResultMixin, DeleteView):
    model = IntegrationRunResult
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('integration-list')

#endregion


#region WebRequest

class WebRequestMixin(CRUDGenericMixin):
    object_type_name = "Web Request"
    object_type_name_plural = "Web Requests"
    object_url_name_slug = "web-request"
    edit_disclaimer = "You can substitute environment variables like ${ENV_VAR}. BE CAREFUL, you can leak secrets if you aren't careful!"


class WebRequestListView(WebRequestMixin, SingleTableView):
    model = WebRequest
    table_class = WebRequestTable
    template_name = "generic_crud_list.html"


class WebRequestDetailView(WebRequestMixin, DetailView):
    model = WebRequest
    template_name = "integration/web_request_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        webrequest = self.object

        # Use the run_history property from IntegrationObject
        run_history_qs = webrequest.run_history

        # Create django-tables2 table
        table = IntegrationRunResultTable(run_history_qs)
        RequestConfig(self.request, paginate={"per_page": 10}).configure(table)

        context["run_history_table"] = table
        return context


class WebRequestCreateView(WebRequestMixin, CreateView):
    model = WebRequest
    form_class = WebRequestForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('web-request-detail', kwargs={'pk': self.object.pk})
    

class WebRequestUpdateView(WebRequestMixin, UpdateView):
    model = WebRequest
    form_class = WebRequestForm
    template_name = "generic_crud_form.html"

    def get_success_url(self):
        return reverse('web-request-detail', kwargs={'pk': self.object.pk})


class WebRequestDeleteView(WebRequestMixin, DeleteView):
    model = WebRequest
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('web-request-list')


class WebRequestTestSendView(View):
    """
    POST-only view to send a WebRequest and redirect back to its detail page.
    """
    def post(self, request, pk):
        web_request = get_object_or_404(WebRequest, pk=pk)
        try:
            result = web_request.run(IntegrationCaller.MANUAL)
            if result.successful:
                messages.success(
                    request,
                    f"Request succeeded. Log:\n{result.run_log}"
                )
            else:
                messages.error(
                    request,
                    f"Request failed. Log:\n{result.run_log}"
                )
        except Exception as e:
            messages.error(request, f"An error occurred while processing the request: {e}")

        return redirect(reverse("web-request-detail", kwargs={"pk": web_request.pk}))

#endregion