from django.contrib import admin
from .models import *
from django import forms

from django.urls import include, re_path, reverse

class PersistentLogAdmin(admin.ModelAdmin):
    search_fields = ["group__name", "user__username", "component", "session__session_id", "session__ip", "message", "request_path"]
    list_display = ('when', 'tid', 'request_method', 'request_path', 'component', 'action')

    def get_readonly_fields(self, request, obj = None):
        return ('message', 'level', 'user', 'group', 'session', 'request_path', 'request_method', 'component', 'action', 'pkey')

    def has_delete_permission(self, request, obj=None):
        return False

    def session_link(self, obj):
        if obj.session is None:
            return "n/a"
        url = reverse('admin:sessionlog_sessionlog_change', args=(obj.session.pk,))
        return '<a href="{0}">{1}</a>'.format(url, obj.session.session_id)
    session_link.allow_tags = True

admin.site.register(PersistentLog, PersistentLogAdmin)

