import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from media.models import Album, Channel, ChannelPhoto, Photo
from media.signals import channel_photo_published
from photoserv_plugin import PhotoservPlugin

from .forms import IntegrationPluginForm
from .models import IntegrationCaller, IntegrationPlugin, PluginStorage, RunResult
from .services import discover_plugin_modules, load_plugin_module
from .tasks import (
    call_integration_plugin_signal,
    queue_global_integrations,
    scan_plugins,
)


PLUGIN_SOURCE = '''
from photoserv_plugin import PhotoservPlugin

__plugin_name__ = "Test Plugin"
__plugin_uuid__ = "80d492e3-cb83-4ad4-9ca3-dbd526d20ed8"
__plugin_version__ = "1.0.0"
__plugin_config__ = {{}}

ORIGIN = "{origin}"

class TestPlugin(PhotoservPlugin):
    def on_global_change(self, **kwargs):
        pass

    def on_photo_publish(self, data, params, **kwargs):
        pass
'''


class TestPlugin(PhotoservPlugin):
    pass


class IntegrationPluginModelTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(name="Model Channel")
        self.plugin = IntegrationPlugin.objects.create(
            nickname="Model Plugin",
            module="test_plugin",
            config={"token": "${INTEGRATION_TEST_TOKEN}"},
            channel=self.channel,
        )

    def test_plugin_has_channel_subscription(self):
        self.assertEqual(self.plugin.channel, self.channel)

    def test_deleting_channel_clears_subscription(self):
        self.channel.delete()
        self.plugin.refresh_from_db()

        self.assertIsNone(self.plugin.channel)

    def test_config_must_be_a_dictionary(self):
        self.plugin.config = ["not", "an", "object"]

        with self.assertRaisesMessage(ValidationError, "valid JSON object"):
            self.plugin.clean()

    def test_config_expands_environment_variables_recursively(self):
        self.plugin.config = {
            "token": "${INTEGRATION_TEST_TOKEN}",
            "nested": ["${INTEGRATION_TEST_TOKEN}"],
        }

        with patch.dict(os.environ, {"INTEGRATION_TEST_TOKEN": "secret"}):
            config = self.plugin._get_config_dict()

        self.assertEqual(config, {"token": "secret", "nested": ["secret"]})

    def test_uuid_is_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            IntegrationPlugin.objects.create(
                uuid=self.plugin.uuid,
                module="duplicate_uuid",
            )

    def test_valid_requires_metadata_and_plugin_subclass(self):
        module = SimpleNamespace(
            __plugin_name__="Valid",
            __plugin_uuid__="47b10b62-a35b-4991-9f74-fe774e93eaa2",
            __plugin_version__="1.0.0",
            __plugin_config__={},
            TestPlugin=TestPlugin,
        )

        with patch("integration.models.load_plugin_module", return_value=module):
            self.assertTrue(self.plugin.valid)

    def test_invalid_when_module_cannot_be_loaded(self):
        with patch("integration.models.load_plugin_module", return_value=None):
            self.assertFalse(self.plugin.valid)

    def test_run_creates_related_success_result(self):
        with patch.object(self.plugin, "_run", return_value="completed"):
            result = self.plugin.run(IntegrationCaller.MANUAL)

        self.assertTrue(result.successful)
        self.assertEqual(result.integration_plugin, self.plugin)
        self.assertEqual(result.run_log, "completed")
        self.assertEqual(list(self.plugin.run_history), [result])
        self.assertEqual(self.plugin.last_run_timestamp, result.start_timestamp)

    def test_run_records_plugin_failure(self):
        with patch.object(self.plugin, "_run", side_effect=RuntimeError("broken")):
            result = self.plugin.run(IntegrationCaller.EVENT_SCHEDULER)

        self.assertFalse(result.successful)
        self.assertEqual(result.integration_plugin, self.plugin)
        self.assertIn("broken", result.run_log)

    def test_deleting_plugin_cascades_to_run_results(self):
        RunResult.objects.create(
            integration_plugin=self.plugin,
            caller=IntegrationCaller.MANUAL,
        )

        self.plugin.delete()

        self.assertFalse(RunResult.objects.exists())


class PluginStorageTests(TestCase):
    def test_storage_keys_are_unique(self):
        PluginStorage.objects.create(key="plugin:key", value={"value": 1})

        with self.assertRaises(IntegrityError), transaction.atomic():
            PluginStorage.objects.create(key="plugin:key", value={"value": 2})


class IntegrationPluginFormTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(name="Form Channel")

    def test_form_accepts_channel_and_json_object_config(self):
        form = IntegrationPluginForm(
            data={
                "nickname": "Form Plugin",
                "module": "form_plugin",
                "config": '{"key": "value"}',
                "channel": self.channel.pk,
                "active": True,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        plugin = form.save()
        self.assertEqual(plugin.channel, self.channel)
        self.assertEqual(plugin.config, {"key": "value"})

    def test_form_rejects_non_object_config(self):
        form = IntegrationPluginForm(
            data={
                "module": "form_plugin",
                "config": '["not", "an", "object"]',
                "channel": "",
                "active": True,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Config must be a JSON object", form.errors["config"][0])


class PluginServiceTests(SimpleTestCase):
    module_names = ("first_only", "second_only", "shared_plugin")

    def tearDown(self):
        for module_name in self.module_names:
            sys.modules.pop(module_name, None)
        super().tearDown()

    def test_discovery_uses_all_paths_and_first_path_wins_duplicates(self):
        with TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            (first / "first_only.py").write_text("VALUE = 1")
            (first / "shared_plugin.py").write_text(PLUGIN_SOURCE.format(origin="first"))
            (first / "_private.py").write_text("VALUE = 1")
            (second / "second_only.py").write_text("VALUE = 2")
            (second / "shared_plugin.py").write_text(PLUGIN_SOURCE.format(origin="second"))

            with override_settings(PLUGINS_PATH=[first, second]):
                modules = discover_plugin_modules()
                loaded_module = load_plugin_module("shared_plugin")

        self.assertEqual(modules, ["first_only", "shared_plugin", "second_only"])
        self.assertEqual(loaded_module.ORIGIN, "first")


class IntegrationReceiverTests(TestCase):
    def test_album_create_update_and_delete_each_queue_global_change(self):
        with patch("integration.receivers.call_queue_global_integrations") as queue_global:
            album = Album.objects.create(title="Receiver Album")
            album.description = "Updated"
            album.save()
            album.delete()

        self.assertEqual(queue_global.call_count, 3)

    def test_photo_publish_queues_channel_scoped_plugin_dispatch(self):
        channel = Channel.objects.create(name="Publishing Channel")
        with patch("integration.receivers.call_queue_global_integrations") as queue_global:
            photo = Photo.objects.create(title="Published Photo", raw_image="published.jpg")
            channel_photo = ChannelPhoto.objects.create(channel=channel, photo=photo)

            with patch(
                "integration.receivers.call_integration_plugin_signal.delay"
            ) as dispatch:
                with self.captureOnCommitCallbacks(execute=True):
                    channel_photo_published.send(Photo, instance=channel_photo)

        dispatch.assert_called_once()
        args, kwargs = dispatch.call_args
        self.assertEqual(args, ("on_photo_publish",))
        self.assertEqual(kwargs["channel_id"], channel.pk)
        self.assertEqual(kwargs["data"]["uuid"], str(photo.uuid))
        queue_global.assert_called()


class IntegrationTaskTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(name="Task Channel")
        self.other_channel = Channel.objects.create(name="Other Task Channel")
        self.matching_plugin = IntegrationPlugin.objects.create(
            nickname="Matching",
            module="matching",
            channel=self.channel,
        )
        self.other_plugin = IntegrationPlugin.objects.create(
            nickname="Other",
            module="other",
            channel=self.other_channel,
        )
        self.inactive_plugin = IntegrationPlugin.objects.create(
            nickname="Inactive",
            module="inactive",
            channel=self.channel,
            active=False,
        )

    def test_photo_publish_calls_only_active_plugins_for_matching_channel(self):
        photo_data = {"uuid": str(uuid.uuid4()), "title": "Photo"}

        with patch.object(
            IntegrationPlugin,
            "valid",
            new=property(lambda plugin: True),
        ), patch.object(IntegrationPlugin, "run") as run:
            result = call_integration_plugin_signal(
                "on_photo_publish",
                data=photo_data,
                channel_id=self.channel.pk,
            )

        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["method_name"], "on_photo_publish")
        self.assertEqual(run.call_args.kwargs["method_args"], (photo_data, {}))
        self.assertEqual(result, "Called on_photo_publish on 1 plugins")

    def test_global_change_calls_every_active_valid_plugin(self):
        with patch.object(
            IntegrationPlugin,
            "valid",
            new=property(lambda plugin: True),
        ), patch.object(IntegrationPlugin, "run") as run:
            result = call_integration_plugin_signal("on_global_change")

        self.assertEqual(run.call_count, 2)
        self.assertEqual(result, "Called on_global_change on 2 plugins")
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["method_name"], "on_global_change")
            self.assertEqual(call.kwargs["method_args"], ())

    def test_invalid_plugin_is_not_called(self):
        with patch.object(
            IntegrationPlugin,
            "valid",
            new=property(lambda plugin: False),
        ), patch.object(IntegrationPlugin, "run") as run:
            result = call_integration_plugin_signal("on_global_change")

        run.assert_not_called()
        self.assertEqual(result, "Called on_global_change on 0 plugins")

    def test_queue_global_integrations_enqueues_global_signal(self):
        with patch("integration.tasks.call_integration_plugin_signal.delay") as dispatch:
            result = queue_global_integrations()

        dispatch.assert_called_once_with("on_global_change")
        self.assertEqual(result, "Queued global integration dispatch.")

    def test_scan_creates_inactive_integrations_for_new_modules_only(self):
        IntegrationPlugin.objects.create(module="existing", active=True)

        with patch(
            "integration.tasks.discover_plugin_modules",
            return_value=["existing", "new_plugin"],
        ):
            result = scan_plugins()

        created = IntegrationPlugin.objects.get(module="new_plugin")
        self.assertFalse(created.active)
        self.assertEqual(IntegrationPlugin.objects.filter(module="existing").count(), 1)
        self.assertEqual(result, "Scanned plugins directory. Created 1 new plugin entries.")


class RunResultTests(TestCase):
    def test_relation_is_optional_for_legacy_cleanup(self):
        result = RunResult.objects.create(caller=IntegrationCaller.EVENT_SCHEDULER)

        self.assertIsNone(result.integration_plugin)

    def test_results_are_ordered_newest_first(self):
        plugin = IntegrationPlugin.objects.create(module="ordered")
        older = RunResult.objects.create(
            integration_plugin=plugin,
            caller=IntegrationCaller.MANUAL,
            start_timestamp=timezone.now() - timedelta(days=1),
        )
        newer = RunResult.objects.create(
            integration_plugin=plugin,
            caller=IntegrationCaller.MANUAL,
            start_timestamp=timezone.now(),
        )

        self.assertEqual(list(plugin.run_results.all()), [newer, older])
