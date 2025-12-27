from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register([RunResult, WebRequest, PythonPlugin, PluginStorage, PhotoPluginExclusion, PluginEntityParameters])
