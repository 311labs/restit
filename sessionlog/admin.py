from django.contrib import admin
from .models import *
from django import forms

class SessionLogAdmin(admin.ModelAdmin):
    pass

admin.site.register(SessionLog, SessionLogAdmin)

