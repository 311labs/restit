from django.contrib import admin
from .models import *


class GroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ('name', 'uuid', 'kind', 'parent')
    fields = ('name', 'short_name', 'kind', 'parent', 'is_active')


class MemberAdmin(admin.ModelAdmin):
    date_hierarchy = "date_joined"
    list_display = ('username', 'email', 'first_name', 'last_name', 'last_login',)
    search_fields = ['email', 'first_name', 'last_name', 'username']
    fields = ('display_name', 'username', 'first_name', 'last_name', 'email', 'is_staff','is_superuser', 'is_active',)


class MembershipAdmin(admin.ModelAdmin):
    raw_id_fields = ['member', 'group']
    date_hierarchy = "created"
    list_display = ('member', 'role', 'group', 'created', 'state',)
    search_fields = ['role', 'member__email', 'member__last_name', 'member__first_name']


class InviteList(admin.ModelAdmin):
    date_hierarchy = "created"
    list_display = ('email', 'name', 'created', 'invited_by', 'approved')
    fields = ('name', 'approved')
    search_fields = ['email', 'name']


class AuthTokenAdmin(admin.ModelAdmin):
    raw_id_fields = ['member']
    date_hierarchy = "created"
    list_display = ('created', 'member')


class MemberDeviceAdmin(admin.ModelAdmin):
    raw_id_fields = ['member']
    date_hierarchy = "created"
    list_display = ('created', 'member', "uuid", "kind")


class SessionAdmin(admin.ModelAdmin):
    raw_id_fields = ['member']
    date_hierarchy = "created"
    list_display = ('created', "last_activity", 'member', "ip", "device")


admin.site.register(Member, MemberAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Membership, MembershipAdmin)
admin.site.register(AuthToken, AuthTokenAdmin)
admin.site.register(MemberDevice, MemberDeviceAdmin)
admin.site.register(AuthSession, SessionAdmin)


