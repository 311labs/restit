from django.contrib import admin
from pushit.models import *

class ProductAdmin(admin.ModelAdmin):
    raw_id_fields = ['owner', 'group', 'library']
    search_fields = ["name"]
    list_display = ('name', 'kind', 'kind')

class ReleaseAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ('created', 'product', 'version_num', 'version_str')


admin.site.register(Product, ProductAdmin)
admin.site.register(Release, ReleaseAdmin)
