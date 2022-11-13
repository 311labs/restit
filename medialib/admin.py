from django.contrib import admin
from .models import *

admin.site.register(MediaLibrary)

admin.site.register(MediaItem)

admin.site.register(MediaItemRendition)

admin.site.register(MediaMeta)

class RenditionPresetAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'stage')
    search_fields = ('name','sort_name')
admin.site.register(RenditionPreset, RenditionPresetAdmin)

class RenditionDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'preset', 'use')
    search_fields = ('name','use')
admin.site.register(RenditionDefinition, RenditionDefinitionAdmin)

admin.site.register(RenditionSet)

class RenditionParameterAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'required')
    search_fields = ('name',)
admin.site.register(RenditionParameter, RenditionParameterAdmin)

class RenditionParameterSettingAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'renditionPreset', 'parameter', 'setting')
    ordering = ('renditionPreset', 'parameter')
admin.site.register(RenditionPresetParameterSetting, RenditionParameterSettingAdmin)

class RenditionDefinitionSettingAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'renditionDefinition', 'parameter', 'setting')
    ordering = ('renditionDefinition', 'parameter')
admin.site.register(RenditionDefinitionParameterSetting, RenditionDefinitionSettingAdmin)

class RenderInstanceAdmin(admin.ModelAdmin):
    list_display = ('instance_id', 'priority', 'state', 'started', 'last_checkin', 'shutdown')
    ordering = ('shutdown', 'priority')
admin.site.register(RenderInstance, RenderInstanceAdmin)

class AccountConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'applicable_preset')
    search_fields = ('name','owner')
admin.site.register(AccountConfig, AccountConfigAdmin)

class AccountConfigSettingAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'accountConfig', 'parameter', 'setting')
    ordering = ('accountConfig', 'parameter')
admin.site.register(AccountConfigParameterSetting, AccountConfigSettingAdmin)

class RenditionSegmentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'rendition', 'start', 'end', 'duration')
    ordering = ('rendition', 'start')
admin.site.register(RenditionSegment, RenditionSegmentAdmin)
