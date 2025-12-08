from django.db import models
from django.db.models import JSONField, TextField
from django.core.exceptions import ValidationError
import requests
import os

# Create your models here.
class WebRequest(models.Model):
    class HttpMethod(models.TextChoices):
        GET = "GET", "GET"
        POST = "POST", "POST"
        PUT = "PUT", "PUT"
        DELETE = "DELETE", "DELETE"
        PATCH = "PATCH", "PATCH"
        HEAD = "HEAD", "HEAD"
        OPTIONS = "OPTIONS", "OPTIONS"

    method = models.CharField(max_length=32, choices=HttpMethod.choices)
    url = models.URLField()
    headers = JSONField()
    body = TextField(blank=True, null=True)

    def clean(self):
        # Ensure headers are in the correct format
        if not isinstance(self.headers, dict):
            raise ValidationError("Headers must be a dictionary.")

    def send(self):
        # Substitute environment variables in the URL and body
        url = self._substitute_env_variables(self.url)
        body = self._substitute_env_variables(self.body) if self.body else None

        # Substitute environment variables in headers
        headers = {key: self._substitute_env_variables(value) for key, value in self.headers.items()}

        # Send the HTTP request
        response = requests.request(self.method, url, headers=headers, data=body)
        return response

    def _substitute_env_variables(self, value):
        # Replace ${ENV_VAR_NAME} with the corresponding environment variable value
        if not value:
            return value
        return os.path.expandvars(value)
