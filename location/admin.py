from django.contrib import admin
from . import models as location
from django import forms


admin.site.register(location.GeoLocation)
admin.site.register(location.GeoPosition)
admin.site.register(location.GeoIP)
# admin.site.register(location.GeoIPLocation)
admin.site.register(location.Address)
