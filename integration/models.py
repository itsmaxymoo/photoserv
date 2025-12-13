from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
import requests
import os
from django.utils.timezone import now
import uuid

    
class IntegrationCaller(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    EVENT_SCHEDULER = "EVENT_SCHEDULER", "Event Scheduler"


class IntegrationRunResult(models.Model):
    """
    Stores a historical record of an integration run.

    - integration_uuid: UUID of the IntegrationObject
    """
    integration_uuid = models.UUIDField(db_index=True, null=True)
    start_timestamp = models.DateTimeField(blank=True, null=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)
    caller = models.CharField(max_length=32, choices=IntegrationCaller.choices)
    successful = models.BooleanField(default=False)
    run_log = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-start_timestamp']

    def __str__(self):
        status = "PASS" if self.successful else "FAIL"
        return f"[{status}] {self.start_timestamp} to {self.end_timestamp} ({self.integration_uuid})"
    
    def get_absolute_url(self):
        return reverse("integration-run-result-detail", kwargs={"pk": self.pk})


class IntegrationObject(models.Model):
    """Base abstract model for all integrations."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    @property
    def integration_type(self) -> str:
        """String name of the class for display/logging."""
        return self.__class__.__name__

    def _run(self) -> str:
        """Subclasses must implement this to perform actual work and return a log string.
        Raise exception on error"""
        raise NotImplementedError()

    def run(self, caller: IntegrationCaller):
        """Execute the integration and automatically record the result."""
        result = IntegrationRunResult.objects.create(
            integration_uuid=self.uuid,
            start_timestamp=now(),
            caller=caller,
        )

        try:
            log_output = self._run()
            result.successful = True
            result.run_log = log_output
        except Exception as e:
            result.successful = False
            result.run_log = f"ERROR: {e}"
        finally:
            result.run_log = result.run_log.strip()
            result.end_timestamp = now()
            result.save()

        return result

    @property
    def run_history(self):
        """Query run history for this integration instance by UUID."""
        return IntegrationRunResult.objects.filter(
            integration_uuid=self.uuid
        ).order_by('-start_timestamp')

    class Meta:
        abstract = True


# Create your models here.
class WebRequest(IntegrationObject):
    class HttpMethod(models.TextChoices):
        GET = "GET", "GET"
        POST = "POST", "POST"
        PUT = "PUT", "PUT"
        DELETE = "DELETE", "DELETE"
        PATCH = "PATCH", "PATCH"
        HEAD = "HEAD", "HEAD"
        OPTIONS = "OPTIONS", "OPTIONS"

    nickname = models.CharField(max_length=255, blank=True, null=True, help_text="Optional")
    method = models.CharField(max_length=32, choices=HttpMethod.choices)
    url = models.URLField()
    headers = models.TextField(blank=True, null=True, default="", help_text="One per line in the format Header: Value")
    body = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def clean(self):
        # Ensure headers are in the correct format
        if self.headers:
            seen_headers = set()
            for line in self.headers.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ':' not in line:
                    raise ValidationError(f"Invalid header format: '{line}'. Each header must contain a colon.")
                header_name = line.split(':', 1)[0].strip()
                if header_name in seen_headers:
                    raise ValidationError(f"Duplicate header found: '{header_name}'.")
                seen_headers.add(header_name)

    def _send(self):
        # Substitute environment variables in the URL and body
        url = self._substitute_env_variables(self.url)
        body = self._substitute_env_variables(self.body) if self.body else None

        # Substitute environment variables in headers
        headers = {}
        if self.headers:
            for line in self.headers.splitlines():
                line = line.strip()
                if line:
                    key, value = map(str.strip, line.split(':', 1))
                    headers[key] = self._substitute_env_variables(value)

        # Send the HTTP request
        response = requests.request(self.method, url, headers=headers, data=body)
        return response
    
    def _run(self):
        log = f"{self.method} {self.url}\n\n{self.headers.rstrip() if self.headers else "(no headers)"}\n\n{self.body.rstrip() if self.body else ""}\n\n"

        try:
            response = self._send()

            log += f"Response: {str(response.status_code)}\n\n{response.text}"

            if not str(response.status_code).startswith("2"):
                raise Exception(log)
        except Exception as e:
            raise Exception(e)

        return log

    def _substitute_env_variables(self, value):
        # Replace ${ENV_VAR_NAME} with the corresponding environment variable value
        if not value:
            return value
        return os.path.expandvars(value)

    def __str__(self):
        return self.nickname if self.nickname else self.method + " " + self.url[:128]

    def get_absolute_url(self):
        return reverse("web-request-detail", kwargs={"pk": self.pk})
    
    class Meta:
        verbose_name = "Web Request"
