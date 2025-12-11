from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse
import requests
import os
from django.utils.timezone import now


class IntegrationRunType(models.TextChoices):
        WEB = "HTTP", "HTTP Request"
        PYTHON = "PYTHON", "Python"
    
class IntegrationCaller(models.TextChoices):
    MANUAL = "MANUAL", "Manual"
    EVENT_SCHEDULER = "EVENT_SCHEDULER", "Event Scheduler"


class IntegrationRunResult(models.Model):
    start_timestamp = models.DateTimeField(blank=True, null=True)
    end_timestamp = models.DateTimeField(blank=True, null=True)
    integration_type = models.CharField(max_length=32, choices=IntegrationRunType.choices)
    integration_object = models.CharField(max_length=255, blank=True, null=True)
    caller = models.CharField(max_length=32, choices=IntegrationCaller.choices)
    successful = models.BooleanField(default=False)
    run_log = models.TextField(blank=True, null=True)


class IntegrationObject:
    def run(self, caller: IntegrationCaller) -> IntegrationRunResult:
        raise NotImplementedError()


# Create your models here.
class WebRequest(models.Model, IntegrationObject):
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

    def send(self):
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
    
    def run(self, caller: IntegrationCaller):
        result = IntegrationRunResult.objects.create(
            start_timestamp=now(),
            integration_type=IntegrationRunType.WEB,
            integration_object=str(self),
            caller=caller
        )

        log = f"{self.method} {self.url}\n{self.headers}\n\n{self.body}"

        try:
            response = self.send()

            log += f"\n\nResponse: {str(response.status_code)}\n\n{response.text}"

            result.successful = str(response.status_code).startswith("2")
        except Exception as e:
            log += str(e)

        result.end_timestamp = now()
        result.run_log = log

        result.save()

        return result

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
