from django.contrib import admin

# Register your models here.
from .models import Visit,EmergencyAlert

admin.site.register(Visit)
admin.site.register(EmergencyAlert)