from django.contrib import admin
from .models import Task, TaskHook
from django import forms


class TaskAdmin(admin.ModelAdmin):
    pass


admin.site.register(Task, TaskAdmin)
admin.site.register(TaskHook)
