from django.contrib import admin
from .models import SMS, PhonenumberInfo
from django import forms


class PhonenumberInfoAdmin(admin.ModelAdmin):
    pass


admin.site.register(PhonenumberInfo, PhonenumberInfoAdmin)
admin.site.register(SMS)

