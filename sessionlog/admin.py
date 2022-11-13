from django.contrib import admin
from .models import *
from django import forms

class SessionLogAdmin(admin.ModelAdmin):
    list_display = ('isActive', 'created', 'ip', 'user', 'user_agent')


admin.site.register(SessionLog, SessionLogAdmin)

