from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django_tables2.views import SingleTableView
from .models import IntegrationCaller, IntegrationPlugin, RunResult
from .forms import IntegrationPluginForm
from .tables import IntegrationPluginTable, IntegrationRunResultTable
from .tasks import call_queue_global_integrations
from photoserv.mixins import CRUDGenericMixin
from django_tables2 import RequestConfig
import json


def redirect_to_home(request):
    return redirect(reverse('integration-list'))


class IntegrationHomeView(PermissionRequiredMixin, TemplateView):
    permission_required = "integration.view_integrationplugin"
    template_name = "integration/integration_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        integrations = IntegrationPlugin.objects.all()
        integrations_table = IntegrationPluginTable(integrations, prefix="integration-")
        RequestConfig(self.request, paginate={"per_page": 10}).configure(integrations_table)
        
        context["integrations_table"] = integrations_table
        
        return context


#region RunResult

class RunResultMixin(CRUDGenericMixin):
    object_type_name = "Integration Run Result"
    object_url_name_slug = "integration-run-result"
    edit_disclaimer = "These are deleted automatically after a while."
    can_directly_create = False
    can_edit = False


class RunResultListView(RunResultMixin, SingleTableView):
    model = RunResult
    table_class = IntegrationRunResultTable
    template_name = "generic_crud_list.html"


class RunResultDetailView(RunResultMixin, DetailView):
    model = RunResult
    template_name = "integration/integration_run_result_detail.html"


class RunResultDeleteView(RunResultMixin, DeleteView):
    model = RunResult
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('integration-list')

#endregion


#region IntegrationPlugin

class IntegrationPluginMixin(CRUDGenericMixin):
    object_type_name = "Integration Plugin"
    object_type_name_plural = "Integration Plugins"
    object_url_name_slug = "integration-plugin"
    edit_disclaimer = "You can substitute environment variables like ${ENV_VAR} in config. THIS IS DANGEROUS! Only use trusted plugins!"


class IntegrationPluginListView(IntegrationPluginMixin, SingleTableView):
    model = IntegrationPlugin

    def get(self, request, *args, **kwargs):
        return redirect(reverse('integration-list'))


class IntegrationPluginDetailView(IntegrationPluginMixin, DetailView):
    model = IntegrationPlugin
    template_name = "integration/integration_plugin_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plugin = self.object

        run_history_qs = plugin.run_results.all()

        # Create django-tables2 table
        table = IntegrationRunResultTable(run_history_qs)
        RequestConfig(self.request, paginate={"per_page": 10}).configure(table)

        context["run_history_table"] = table
        
        # Add plugin metadata if valid
        if plugin.valid:
            try:
                plugin_module = plugin._load_module()
                if plugin_module:
                    context["plugin_name"] = getattr(plugin_module, '__plugin_name__', 'Unknown')
                    context["plugin_version"] = getattr(plugin_module, '__plugin_version__', 'Unknown')
                    context["plugin_uuid"] = getattr(plugin_module, '__plugin_uuid__', 'Unknown')
                    context["plugin_author"] = getattr(plugin_module, '__plugin_author__', 'Unknown')
                    context["plugin_website"] = getattr(plugin_module, '__plugin_website__', 'Unknown')
                    
                    # Get schema dictionaries
                    plugin_config = getattr(plugin_module, '__plugin_config__', {})
                    plugin_entity_params = getattr(plugin_module, '__plugin_entity_parameters__', {})
                    
                    # Store raw dicts for conditional checks
                    context["plugin_config"] = plugin_config
                    context["plugin_entity_parameters"] = plugin_entity_params
                    
                    # Pretty-print as JSON for display
                    if plugin_config:
                        context["plugin_config_json"] = json.dumps(plugin_config, indent=2)
                    if plugin_entity_params:
                        context["plugin_entity_parameters_json"] = json.dumps(plugin_entity_params, indent=2)
            except Exception:
                pass
        
        # Pretty-print the supplied config JSON
        if plugin.config:
            context["config_pretty"] = json.dumps(plugin.config, indent=2)
        else:
            context["config_pretty"] = None
        
        return context


class IntegrationPluginCreateView(IntegrationPluginMixin, CreateView):
    model = IntegrationPlugin
    form_class = IntegrationPluginForm
    template_name = "integration/integration_plugin_form.html"

    def get_success_url(self):
        return reverse('integration-plugin-detail', kwargs={'pk': self.object.pk})


class IntegrationPluginUpdateView(IntegrationPluginMixin, UpdateView):
    model = IntegrationPlugin
    form_class = IntegrationPluginForm
    template_name = "integration/integration_plugin_form.html"

    def get_success_url(self):
        return reverse('integration-plugin-detail', kwargs={'pk': self.object.pk})


class IntegrationPluginDeleteView(IntegrationPluginMixin, DeleteView):
    model = IntegrationPlugin
    template_name = 'confirm_delete_generic.html'

    def get_success_url(self):
        return reverse('integration-plugin-list')


class IntegrationPluginTestRunView(PermissionRequiredMixin, View):
    """
    POST-only view to test run an integration plugin and redirect back to its detail page.
    """
    permission_required = "integration.change_integrationplugin"
    def post(self, request, pk):
        plugin = get_object_or_404(IntegrationPlugin, pk=pk)
        try:
            result = plugin.run(IntegrationCaller.MANUAL, method_name="on_global_change", method_args=())
            if result.successful:
                messages.success(
                    request,
                    f"Plugin test succeeded. Log:\n{result.run_log}"
                )
            else:
                messages.error(
                    request,
                    f"Plugin test failed. Log:\n{result.run_log}"
                )
        except Exception as e:
            messages.error(request, f"An error occurred while processing the plugin: {e}")

        return redirect(reverse("integration-plugin-detail", kwargs={"pk": plugin.pk}))


class QueueGlobalIntegrationsView(PermissionRequiredMixin, View):
    """
    View to manually trigger global integrations.
    """
    permission_required = "integration.change_integrationplugin"
    def post(self, request):
        call_queue_global_integrations()
        messages.success(request, "Queued global integration dispatch.")
        return redirect(reverse("integration-list"))


#endregion
