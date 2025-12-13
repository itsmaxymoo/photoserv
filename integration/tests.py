from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from django.utils.timezone import now
from .models import WebRequest, IntegrationRunResult, IntegrationCaller
import uuid


class WebRequestTests(TestCase):

    def setUp(self):
        self.webreq = WebRequest.objects.create(
            method=WebRequest.HttpMethod.GET,
            url="https://example.com",
            headers="Authorization: Bearer token123",
        )

    def test_run_creates_integration_run_result(self):
        """1. Running a WebRequest creates an IntegrationRunResult tied to this integration."""
        with patch.object(WebRequest, "_send") as mock_send:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_send.return_value = mock_response

            result = self.webreq.run(IntegrationCaller.MANUAL)

        self.assertIsInstance(result, IntegrationRunResult)
        self.assertEqual(result.integration_uuid, self.webreq.uuid)
        self.assertTrue(result.successful)
        self.assertIn("GET https://example.com", result.run_log)
        self.assertEqual(
            IntegrationRunResult.objects.filter(integration_uuid=self.webreq.uuid).count(),
            1
        )

    @patch("integration.models.requests.request")
    def test_mock_http_request_success(self, mock_request):
        """2. Mock a webrequest HTTP request (200 success)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_request.return_value = mock_response

        result = self.webreq.run(IntegrationCaller.MANUAL)

        mock_request.assert_called_once_with(
            "GET",
            "https://example.com",
            headers={"Authorization": "Bearer token123"},
            data=None,
        )
        self.assertTrue(result.successful)
        self.assertIn("Response: 200", result.run_log)
        self.assertIn("Success", result.run_log)

    @patch("integration.models.requests.request")
    def test_mock_http_request_failure(self, mock_request):
        """3. Mock non-200 response → failed IntegrationRunResult."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        result = self.webreq.run(IntegrationCaller.EVENT_SCHEDULER)

        self.assertFalse(result.successful)
        self.assertIn("Internal Server Error", result.run_log)
        self.assertIn("ERROR", result.run_log)

    def test_header_validation(self):
        """4. Test various combinations of valid and invalid HTTP headers."""

        # Valid: multiple distinct headers
        valid = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization: Bearer 123\nContent-Type: application/json",
        )
        try:
            valid.clean()  # should not raise
        except ValidationError:
            self.fail("Valid headers raised ValidationError unexpectedly.")

        # Invalid: missing colon
        invalid_no_colon = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization Bearer 123",
        )
        with self.assertRaises(ValidationError) as cm:
            invalid_no_colon.clean()
        self.assertIn("Invalid header format", str(cm.exception))

        # Invalid: duplicate header name
        invalid_duplicate = WebRequest(
            method="GET",
            url="https://example.com",
            headers="Authorization: token1\nAuthorization: token2",
        )
        with self.assertRaises(ValidationError) as cm:
            invalid_duplicate.clean()
        self.assertIn("Duplicate header", str(cm.exception))

        # Valid: empty or blank headers
        empty = WebRequest(method="GET", url="https://example.com", headers="")
        try:
            empty.clean()
        except ValidationError:
            self.fail("Empty headers should not raise ValidationError.")
