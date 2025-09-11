from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls import reverse


# Create your models here.
class User(AbstractUser):

    def get_absolute_url(self):
        return reverse("user-detail", kwargs={"pk": self.pk})
    

    def __str__(self):
        return self.username
