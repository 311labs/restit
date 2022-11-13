from django.db import models
from django.db.models import Q
from django.conf import settings
import re

from rest.models import RestModel, MetaDataModel, MetaDataBase, RestValidationError, PermisionDeniedException
from rest import helpers as rest_helpers
from rest import RemoteEvents
from rest import crypto
from rest import mail as rest_mail
from rest.views import restPermissionDenied

from .member import Member


MEMBERSHIP_ROLES = getattr(settings, "MEMBERSHIP_ROLES", None)


class Group(models.Model, RestModel, MetaDataModel):
    """
    Group Model allows for the grouping of other models and works with Member throug Membership Model

    parent allows for tree based heirachy of groups
    children allows for manytomany relationships with other groups
    kind is heavily used to filter different kinds of groups
    """
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    uuid = models.CharField(db_index=True, max_length=64, blank=True, null=True, default=None)
    name = models.CharField(db_index=True, max_length=200)
    short_name = models.CharField(max_length=60, null=True, blank=True, default=None)
    kind = models.CharField(db_index=True, max_length=80, default="org")
    parent = models.ForeignKey("Group", default=None, null=True, blank=True, related_name="groups", on_delete=models.CASCADE)

    is_active = models.BooleanField(default=True, blank=True)
    # this is the new model for groups having multiple parents
    children = models.ManyToManyField("self", related_name="parents", symmetrical=False)

    class RestMeta:
        SEARCH_FIELDS = [
            "name",
            "short_name",
        ]
        LIST_DEFAULT_FILTERS = {
            "is_active": True
        }
        POST_SAVE_FIELDS = ["child_of"]
        VIEW_PERMS = ["view_all_groups", "is_terminal"]
        CREATE_PERMS = ["manage_groups", "create_groups"]
        GRAPHS = {
            "basic": {
                "fields": [
                    "id",
                    "uuid",
                    "name",
                    "short_name",
                    "kind",
                    "created",
                    "thumbnail",
                    "is_active",
                    "timezone"
                ]
            },
            "default": {
                "graphs": {
                    "self": "basic",
                    "parent": "basic"
                },
                "fields": ["metadata"],
            },
            "detailed": {
                "graphs": {
                    "self": "basic",
                    "parent": "basic",
                    "children": "basic"
                },
                "fields": ["metadata"],
            },
            "abstract": {
                "fields": [
                    ('uuid', 'id'),
                    "name",
                    "kind",
                    "timezone"
                ]
            }
        }

    @property
    def timezone(self):
        return self.getProperty("timezone", "America/Los_Angeles")

    @property
    def timezone_short(self):
        zone = self.getProperty("timezone", "America/Los_Angeles")
        return rest_helpers.getShortTZ(zone)

    @property
    def file_safe_name(self):
        return re.sub("[^0-9a-zA-Z]+", "_", self.name.lower())

    def thumbnail(self, name="default"):
        lib = self.libraries.filter(name=name).first()
        if lib:
            item = lib.items.all().first()
            if item:
                return item.thumbnail_url()
        return None
        
    @classmethod
    def on_rest_list_filter(cls, request, qset=None):
        # override on do any pre filters
        child_of = request.DATA.get("child_of")
        if request.group is not None and child_of is None:
            child_of = request.group.id
        parent_id = request.DATA.get(["parent", "parent_id"])
        if parent_id:
            parent = request.member.getGroup(parent_id)
            if not parent:
                raise PermisionDeniedException("invalid parent")
            qset = qset.filter(parent=parent)
        elif child_of:
            parent = Group.objects.filter(pk=child_of).last()
            if parent:
                request.group = None
                return parent.getAllChildren()
        else:
            no_parent = request.DATA.get("no_parent")
            has_parent = request.DATA.get("has_parent")
            if no_parent:
                qset = qset.filter(parent=None)
            elif has_parent:
                qset = qset.exclude(parent=None)
            else:
                is_parent = request.DATA.get("is_parent", False, field_type=bool)
                if is_parent:
                    qset = qset.exclude(groups=None)
        if not request.member.hasPermission("view_all_groups"):
            qset = qset.filter(memberships__member=request.member, memberships__state__gte=-10)
        return qset

    def on_rest_get(self, request):
        if (request.member and request.member.isMemberOf(self)) or self.on_rest_can_get(request):
            return self.restGet(request)
        return restPermissionDenied(request)

    def onRestCanSave(self, request):
        if request.member is None:
            raise PermisionDeniedException("permission denied for save")
        if request.member.hasPermission(["manage_groups", "create_groups"]):
            return True
        if self.checkPermission(request.member, ["manage_settings", "manage_members"]):
            return True
        raise PermisionDeniedException("permission denied for save")

    def on_rest_pre_save(self, request, **kwargs):
        pass

    def on_rest_saved(self, request, is_new=False):
        if request.member:
            note = "edited group {}:{}\n{}".format(self.name, self.pk, request.DATA.asDict())
            request.member.log("group_edit", note, method="group")
            self.logEvent("group_edit", component="account.Member", component_id=request.member.id, note=note)

    def set_child_of(self, value):
        # this is a helper to add this group to another group
        parent = Group.objects.filter(pk=value).last()
        if parent and parent.pk != self.pk:
            if not parent.children.filter(pk=self.pk).exists() and not self.hasChild(parent) and self.kind != "org":
                parent.children.add(self)

    def set_remove_parent(self, value):
        parent = Group.objects.filter(pk=value).last()
        if parent:
            if parent.children.filter(pk=self.pk).exists():
                parent.children.remove(self)

    def getAllChildren(self, include_me=False):
        if include_me:
            return Group.objects.filter(Q(parent=self)| Q(parents=self)| Q(pk=self.id))
        return Group.objects.filter(Q(parent=self)| Q(parents=self))

    def getAllChildrenIds(self):
        return list(self.getAllChildren().values_list("id", flat=True))

    def hasChild(self, group):
        if not group:
            return False
        if self.children.filter(pk=group.pk).exists():
            return True
        for child in self.children.all():
            if child.hasChild(group):
                return True
        return False

    def getParentOfKind(self, kind):
        if self.parent and self.parent.kind == kind:
            return self.parent
        group = self.parents.filter(kind=kind).first()
        if group:
            return group
        for parent in self.parents.all():
            if parent.kind == kind:
                return parent
            group = parent.getParentOfKind(kind)
            if group:
                return group
        return None

    def hasParent(self, group):
        # this needs to check parents...then check each parent for parent
        if self.parent == group:
            return True
        if self.parents.filter(pk=group.id).count():
            return True
        for parent in self.parents.all():
            if parent == group:
                return True
            if parent.hasParent(group):
                return True
        return False

    def notifyMembers(self, subject, message=None, template=None, context=None, email_only=False, sms_msg=None, perms=None, force=False):
        if perms is not None:
            members = self.getMembers(perms=perms, as_member=True)
        else:
            Member = RestModel.getModel("account", "Member")
            members = Member.objects.filter(is_active=True, memberships__group=self, memberships__state__gte=-10)
        NotificationRecord = RestModel.getModel("account", "NotificationRecord")
        NotificationRecord.notify(members, subject, message, template, context, email_only, sms_msg, force)

    def hasPerm(self, member, perm, staff_override=True, check_member=False):
        return self.checkPermission(member, perm, staff_override, check_member)

    def checkPermission(self, member, perm, staff_override=True, check_member=False):
        if member.is_superuser:
            return True
        if staff_override and member.is_staff:
            return True
        if check_member:
            if member.hasPerm(perm) or member.hasGroupPerm(self, perm):
                return True
        memberships = member.memberships.filter(group=self)
        for ms in memberships:
            if ms.hasPermission(perm):
                return True
        return False

    def getLocalTime(self, when=None):
        zone = self.getProperty("timezone", "America/Los_Angeles")
        return rest_helpers.convertToLocalTime(zone, when)

    def getUTC(self, when):
        zone = self.getProperty("timezone", "America/Los_Angeles")
        return rest_helpers.convertToUTC(zone, when)

    def getBusinessDay(self, start=None, end=None, kind="day"):
        zone = self.getProperty("timezone", "America/Los_Angeles")
        eod = self.getProperty("eod", 0, field_type=int)
        return rest_helpers.getDateRangeZ(start, end, kind, zone, hour=eod)

    def getOperatingHours(self, start=None, end=None, kind="day"):
        # deprecate this, operating hours is deceptive
        zone = self.getProperty("timezone", "America/Los_Angeles")
        eod = self.getProperty("eod", 0, field_type=int)
        return rest_helpers.getDateRangeZ(start, end, kind, zone, hour=eod)

    def getTimeZoneOffset(self, when=None, hour=None):
        zone = self.getProperty("timezone", "America/Los_Angeles")
        return rest_helpers.getTimeZoneOffset(zone, when, hour=hour)

    def getEOD(self, eod=None, onday=None, in_local=False):
        if eod is None:
            eod = self.getProperty("eod", 0, field_type=int)
            if in_local:
                return eod
        offset = self.getTimeZoneOffset(onday, hour=eod)
        return offset

    def updateUUID(self):
        self.uuid = crypto.obfuscateID("group", self.id)
        self.save()

    def isMember(self, member):
        return self.memberships.filter(member=member, state__gte=-10).count()

    def hasMember(self, member):
        return self.isMember(member)

    def addMember(self, member, role):
        return self.addMembership(member, role)

    def addMembership(self, member, role):
        if self.memberships.filter(member=member, role=role).count():
            return None
        Membership = RestModel.getModel("account", "Membership")
        ms = Membership(group=self, member=member, role=role)
        ms.save()
        return ms

    def getMembers(self, perms=None, role=None, as_member=False):
        if perms:
            if type(perms) in [str, str]:
                perms = [perms]
        if role:
            if type(role) in [str, str]:
                role = [role]

        if as_member:
            Member = RestModel.getModel("account", "Member")
            res = Member.objects.filter(is_active=True, memberships__group=self, memberships__state__gte=-10)
            if perms:
                res = res.filter(memberships__group=self, memberships__permissions__name__in=perms)
            if role:
                res = res.filter(memberships__group=self, memberships__role__in=role)
            return res.distinct()
        res = self.memberships.filter(state__gte=-10)
        if perms:
            res = res.filter(permissions__name__in=perms)
        if role:
            res = res.filter(role__in=role)
        return res.distinct()

    def getMembership(self, member):
        return self.memberships.filter(member=member).first()

    def invite(self, member, role="guest"):
        # invite a user to this group
        Membership = RestModel.getModel("account", "Membership")
        ms = Membership.objects.filter(group=self, member=member).last()
        if ms is None:
            ms = Membership(member=member, group=self, role=role)
            ms.save()
        elif ms.role != role:
            ms.clearPermissions()
        if MEMBERSHIP_ROLES:
            perms = MEMBERSHIP_ROLES.get(role, [])
            for k in perms:
                ms.setProperty(k, 1, category="permissions")
        return ms

    def getEmails(self, role=None, perms=None, master_perm=None):
        emails = []
        members = self.getMembers(role=role, perms=perms, as_member=True)
        for m in members:
            if "invalid" in m.email:
                continue
            emails.append(m.email)
        if master_perm:
            emails = emails + Member.GetWithPermission(master_perm, email_list=True)
        return emails

    def sendEmail(self, role=None, perms=None, subject="Notification", template="email/base", body="", context={}, master_perm=None):
        c = {
            'settings':settings,
            'subject':subject,
            'from': settings.DEFAULT_FROM_EMAIL,
            "body": body,
            'group': self,
            'sent_to': None,
        }
        sent_to = []
        c.update(context)
        members = self.getMembers(role=role, perms=perms, as_member=True)
        for m in members:
            if "invalid" in m.email:
                continue
            # print m.email
            c["to"] = m.email
            sent_to.append(m.email)
            c["user"] = m
            rest_mail.render_to_mail(template, c)

        if master_perm:
            c["to"] = Member.GetWithPermission(master_perm, email_list=True)
            c["sent_to"] = c["to"]
            if c["to"]:
                rest_mail.render_to_mail(template, c)

    def sendEvent(self, name, message, custom=None):
        if not custom:
            custom = {}
        custom["group_id"] = self.id
        RemoteEvents.sendToGroup(
            self,
            name,
            message=message,
            custom=custom)

    def sendChangeEvent(self, model, model_pk, name="group.change", custom=None):
        if not custom:
            custom = {}
        custom["group_id"] = self.id
        RemoteEvents.sendToGroup(
            self,
            name,
            model=model,
            model_id=model_pk,
            custom=custom)

    def getStats(self):
        return {
            "members": self.memberships.count(),
            "active": self.memberships.filter(state__gte=0).count(),
            "pending_invites": self.memberships.filter(state__in=[-10,-9]).count()
        }

    def logEvent(self, kind, component=None, component_id=None, note=None):
        GroupFeed = RestModel.getModel("account", "GroupFeed")
        return GroupFeed.log(self.getActiveRequest().member, self, kind, component, component_id, note)

    def __str__(self):
        return F"{self.name}:{self.id}"

    @classmethod
    def canSubscribeTo(cls, credentials, msg):
        # this is called by the ws4redis framework when a websocket is requesting a subscription
        # credentials are the authentication details for the websocket
        # the response is expected to be a list of primary keys these credentials have access to
        # or the single pk if msg.pk is not none if the creds have access to that key
        if credentials.kind == "member":
            rest_helpers.log_error(msg)
            if msg.pk is not None:
                if credentials.member.hasPermission("view_all_groups") or credentials.member.isMemberOf(msg.pk):
                    return [msg.pk]
                return None
            return credentials.member.getGroupIDs()
        return None

    @classmethod
    def canPublishTo(cls, credentials, msg):
        # this is called by the ws4redis framework when a websocket wants to publish to a channel
        # credentials are the authentication details for the websocket
        # this should return true or false
        if credentials.kind == "member":
            if msg.pk is not None:
                return credentials.member.isMemberOf(msg.pk)
        return False         


class GroupMetaData(MetaDataBase):
    parent = models.ForeignKey(Group, related_name="properties", on_delete=models.CASCADE)




