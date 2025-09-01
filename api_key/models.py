from django.db import models
from django.contrib.auth.hashers import make_password, check_password
import secrets
from django.utils import timezone
from datetime import timedelta


def default_expiration() -> timezone:
    return timezone.now() + timedelta(days=90)


class APIKey(models.Model):
    name = models.CharField(max_length=128)
    description = models.CharField(max_length=512, blank=True, null=True)
    hash = models.CharField(max_length=128, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField(default=default_expiration)
    read_only = models.BooleanField(default=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_on

    @staticmethod
    def create_key(name: str) -> str:
        """
        Generates a raw API key and saves its hash in the DB.
        Returns the raw key (only shown once).
        """
        secret_key = secrets.token_urlsafe(32)
        hash = make_password(secret_key)
        APIKey.objects.create(name=name, hash=hash)
        return secret_key

    def check_key(self, raw_key: str) -> bool:
        return not self.is_expired() and check_password(raw_key, self.hash)
