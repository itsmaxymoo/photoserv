from datetime import datetime, time, timezone as datetime_timezone
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from media import services
from media.filters import PhotoFilter
from media.forms import ChannelPublicationHelperForm
from media.models import Channel, ChannelPhoto, Photo
from media.views import ChannelPublicationHelperView


UTC = datetime_timezone.utc


class PublicationScheduleTests(SimpleTestCase):
    def test_schedule_is_evenly_distributed_inside_daily_window(self):
        schedule = services.calculate_publication_schedule(
            3,
            datetime(2026, 1, 5, 9, tzinfo=UTC),
            datetime(2026, 1, 5, 17, tzinfo=UTC),
            weekdays=[0],
            day_start=time(9),
            day_end=time(17),
        )

        self.assertEqual(
            schedule,
            [
                datetime(2026, 1, 5, 9, tzinfo=UTC),
                datetime(2026, 1, 5, 13, tzinfo=UTC),
                datetime(2026, 1, 5, 17, tzinfo=UTC),
            ],
        )

    def test_schedule_skips_unselected_days_and_clips_boundary_days(self):
        schedule = services.calculate_publication_schedule(
            3,
            datetime(2026, 1, 9, 12, tzinfo=UTC),  # Friday
            datetime(2026, 1, 12, 12, tzinfo=UTC),  # Monday
            weekdays=[0, 4],
            day_start=time(9),
            day_end=time(17),
        )

        self.assertEqual(
            schedule,
            [
                datetime(2026, 1, 9, 12, tzinfo=UTC),
                datetime(2026, 1, 9, 16, tzinfo=UTC),
                datetime(2026, 1, 12, 12, tzinfo=UTC),
            ],
        )

    def test_jitter_is_applied_to_each_calculated_time(self):
        class PredictableRandom:
            offsets = iter((-2, 2))

            def randint(self, minimum, maximum):
                self.assertEqual((minimum, maximum), (-2, 2))
                return next(self.offsets)

            def assertEqual(self, left, right):
                if left != right:
                    raise AssertionError(f"{left!r} != {right!r}")

        schedule = services.calculate_publication_schedule(
            2,
            datetime(2026, 1, 5, 9, tzinfo=UTC),
            datetime(2026, 1, 5, 10, tzinfo=UTC),
            weekdays=[0],
            day_start=time(9),
            day_end=time(10),
            jitter_minutes=2,
            rng=PredictableRandom(),
        )

        self.assertEqual(schedule[0], datetime(2026, 1, 5, 8, 58, tzinfo=UTC))
        self.assertEqual(schedule[1], datetime(2026, 1, 5, 10, 2, tzinfo=UTC))

    def test_rates_only_count_selected_weekdays(self):
        rates = services.calculate_publication_rates(
            6,
            datetime(2026, 1, 5, tzinfo=UTC),
            datetime(2026, 1, 11, 23, 59, tzinfo=UTC),
            weekdays=[0, 2, 4],
        )

        self.assertEqual(rates.eligible_days, 3)
        self.assertEqual(rates.per_day, 2)
        self.assertEqual(rates.per_week, 6)
        self.assertEqual(rates.per_month, 26)

    def test_schedule_rejects_a_range_without_eligible_times(self):
        with self.assertRaisesMessage(ValueError, "no eligible publication times"):
            services.calculate_publication_schedule(
                1,
                datetime(2026, 1, 5, 9, tzinfo=UTC),
                datetime(2026, 1, 5, 10, tzinfo=UTC),
                weekdays=[1],
                day_start=time(9),
                day_end=time(10),
            )


class ChannelPublicationHelperFormTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(name="Form target")
        self.valid_data = {
            "channel": self.channel.pk,
            "start_datetime": "2026-01-05T09:00",
            "end_datetime": "2026-01-06T17:00",
            "weekdays": ["0", "1"],
            "time_start": "09:00",
            "time_end": "17:00",
            "jitter": "0",
            "conflict_resolution": "skip",
            "filter_query": "title=test",
        }

    def test_defaults_select_every_weekday_and_disable_respect_default(self):
        form = ChannelPublicationHelperForm(channel=self.channel)

        self.assertEqual(form.initial["channel"], self.channel)
        self.assertEqual(form.fields["weekdays"].initial, tuple(range(7)))
        self.assertFalse(form.fields["respect_default_channel"].initial)
        self.assertEqual(form.fields["time_start"].initial, time(0, 0))
        self.assertEqual(form.fields["time_end"].initial, time(23, 59))

    def test_end_datetime_cannot_precede_start(self):
        data = {**self.valid_data, "end_datetime": "2026-01-05T08:59"}
        form = ChannelPublicationHelperForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn("end_datetime", form.errors)

    def test_at_least_one_weekday_is_required(self):
        data = {**self.valid_data, "weekdays": []}
        form = ChannelPublicationHelperForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn("weekdays", form.errors)

    def test_time_window_must_have_positive_length(self):
        data = {**self.valid_data, "time_end": "09:00"}
        form = ChannelPublicationHelperForm(data)

        self.assertFalse(form.is_valid())
        self.assertIn("time_end", form.errors)


class ChannelPublicationHelperViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="publication-helper-user",
            password="password",
        )
        self.client.force_login(
            self.user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        self.default_channel = Channel.get_default_channel()
        self.target_channel = Channel.objects.create(name="Target channel")
        self.first = Photo.objects.create(
            title="Selected first",
            raw_image="first.jpg",
            canonical_publish_date=datetime(2025, 1, 1, tzinfo=UTC),
        )
        self.second = Photo.objects.create(
            title="Selected second",
            raw_image="second.jpg",
            canonical_publish_date=datetime(2025, 1, 2, tzinfo=UTC),
        )
        self.other = Photo.objects.create(
            title="Not included",
            raw_image="other.jpg",
            canonical_publish_date=datetime(2025, 1, 3, tzinfo=UTC),
        )

    def helper_data(self, **overrides):
        data = {
            "channel": self.target_channel.pk,
            "start_datetime": "2026-01-05T09:00",
            "end_datetime": "2026-01-05T17:00",
            "weekdays": ["0"],
            "time_start": "09:00",
            "time_end": "17:00",
            "jitter": "0",
            "conflict_resolution": "skip",
            "filter_query": "title=Selected",
        }
        data.update(overrides)
        return data

    def post_plan(self, **overrides):
        response = self.client.post(
            reverse("channel-publication-helper"),
            self.helper_data(**overrides),
        )
        self.assertEqual(response.status_code, 302, response.context)
        token = parse_qs(urlparse(response.url).query)["token"][0]
        return token, response

    def test_filter_and_form_pair_selects_the_complete_filtered_queryset(self):
        response = self.client.get(
            reverse("channel-publication-helper"),
            {"title": "Selected", "channel": self.target_channel.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_photo_count"], 2)
        self.assertContains(response, self.first.title)
        self.assertContains(response, self.second.title)
        self.assertNotContains(response, self.other.title)
        self.assertIsInstance(response.context["filter"], PhotoFilter)
        self.assertEqual(
            int(response.context["form"]["channel"].value()),
            self.target_channel.pk,
        )

    def test_confirmation_back_link_preserves_photo_filter_selection(self):
        _, response = self.post_plan()

        confirmation = self.client.get(response.url)
        back_url = confirmation.context["back_url"]
        back_response = self.client.get(back_url)

        self.assertContains(confirmation, f'href="{back_url.replace("&", "&amp;")}"')
        self.assertEqual(back_response.context["selected_photo_count"], 2)
        self.assertEqual(
            back_response.context["filter"].form["title"].value(),
            "Selected",
        )
        self.assertEqual(
            int(back_response.context["form"]["channel"].value()),
            self.target_channel.pk,
        )

    def test_photo_selection_table_defaults_to_five_rows_per_page(self):
        for index in range(5):
            Photo.objects.create(
                title=f"Selected extra {index}",
                raw_image=f"extra-{index}.jpg",
                canonical_publish_date=datetime(2025, 2, index + 1, tzinfo=UTC),
            )

        response = self.client.get(
            reverse("channel-publication-helper"),
            {"title": "Selected"},
        )

        table = response.context["photo_table"]
        self.assertEqual(table.paginator.per_page, 5)
        self.assertEqual(len(table.page.object_list), 5)
        self.assertEqual(response.context["selected_photo_count"], 7)

    def test_skip_conflicts_are_previewed_and_not_replaced(self):
        old_date = datetime(2024, 1, 1, tzinfo=UTC)
        existing = ChannelPhoto.objects.create(
            channel=self.target_channel,
            photo=self.first,
            publish_date=old_date,
        )
        token, response = self.post_plan()

        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, "Skip")
        self.assertContains(confirmation, "Publish")

        confirmed = self.client.post(
            reverse("channel-publication-helper-confirm"),
            {"token": token},
        )
        self.assertRedirects(
            confirmed,
            reverse("channel-detail", kwargs={"pk": self.target_channel.pk}),
        )
        existing.refresh_from_db()
        self.assertEqual(existing.publish_date, old_date)
        self.assertTrue(
            ChannelPhoto.objects.filter(channel=self.target_channel, photo=self.second).exists()
        )

    def test_recreate_conflicts_replaces_the_existing_publication(self):
        existing = ChannelPhoto.objects.create(
            channel=self.target_channel,
            photo=self.first,
            publish_date=datetime(2024, 1, 1, tzinfo=UTC),
            published=True,
        )
        token, response = self.post_plan(conflict_resolution="recreate")

        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, "Republish")
        self.client.post(
            reverse("channel-publication-helper-confirm"),
            {"token": token},
        )

        replacement = ChannelPhoto.objects.get(
            channel=self.target_channel,
            photo=self.first,
        )
        self.assertNotEqual(replacement.pk, existing.pk)
        self.assertEqual(
            replacement.publish_date,
            timezone.make_aware(datetime(2026, 1, 5, 9)),
        )
        self.assertFalse(replacement.published)

    def test_respect_default_copies_unpublished_date_and_schedules_published_photo(self):
        copied_date = datetime(2026, 2, 1, 15, 30, tzinfo=UTC)
        ChannelPhoto.objects.create(
            channel=self.default_channel,
            photo=self.first,
            publish_date=datetime(2025, 1, 1, tzinfo=UTC),
            published=True,
        )
        ChannelPhoto.objects.create(
            channel=self.default_channel,
            photo=self.second,
            publish_date=copied_date,
            published=False,
        )

        token, response = self.post_plan(respect_default_channel="on")
        plan = self.client.session[ChannelPublicationHelperView.session_key][token]
        entries = {entry["photo_id"]: entry for entry in plan["entries"]}

        self.assertEqual(entries[self.first.pk]["date_source"], "schedule")
        self.assertEqual(entries[self.second.pk]["date_source"], "default_channel")
        self.assertEqual(
            datetime.fromisoformat(entries[self.second.pk]["publish_date"]),
            copied_date,
        )
        self.assertEqual(plan["scheduled_count"], 1)
        self.assertEqual(plan["copied_count"], 1)

        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, "Default channel")
        self.client.post(
            reverse("channel-publication-helper-confirm"),
            {"token": token},
        )
        self.assertEqual(
            ChannelPhoto.objects.get(channel=self.target_channel, photo=self.second).publish_date,
            copied_date,
        )

    def test_entry_point_buttons_link_to_helper_and_channel_prefills(self):
        helper_url = reverse("channel-publication-helper")

        photo_list = self.client.get(reverse("photo-list"))
        self.assertContains(photo_list, helper_url)
        channel_detail = self.client.get(
            reverse("channel-detail", kwargs={"pk": self.target_channel.pk})
        )
        self.assertContains(
            channel_detail,
            f"{helper_url}?channel={self.target_channel.pk}",
        )
