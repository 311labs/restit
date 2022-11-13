from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.hashers import check_password
from django.contrib.sessions.models import Session
from django.conf import settings

from datetime import datetime, timedelta
import time
import re
import hashlib
import uuid

from auditlog.models import PersistentLog
from sessionlog.models import SessionLog

from location.models import GeoIP
from rest import RemoteEvents
from rest.models import RestModel, MetaDataModel, MetaDataBase, RestValidationError, PermisionDeniedException
from rest.fields import FormattedField
from rest import helpers as rest_helpers
from rest import mail as rest_mail
from rest import crypto
try:
    import pyotp
except Exception:
    pyotp = None


# we need bigger usernames, in particular for RemoteMember
AbstractUser._meta.get_field('username').max_length = 128
AUTH_CODE_EXPIRES_SECS = getattr(settings, "AUTH_CODE_EXPIRES_SECS", 1440)


class User(AbstractUser, RestModel):
    class Meta:
        db_table = 'auth_user'

    class RestMeta:
        NO_SHOW_FIELDS = ["password"]

    def getMember(self):
        return Member.getByUser(self)

    def log(self, action, message, request=None, group=None, path=None, method=None, level=0):
        # message, level=0, request=None, component=None, pkey=None, action=None, group=None, path=None, method=None
        component = "account.Member"
        pkey = self.id
        PersistentLog.log(message=message, level=level, action=action, request=request, component=component, pkey=pkey, group=group, path=path, method=method)

    def getGroups(self):
        Group = RestModel.getModel("account", "Group")
        return Group.objects.filter(memberships__member=self, memberships__state__gte=-10).distinct()

    def getGroupIDs(self):
        return list(self.getGroups().values_list("pk", flat=True))

    def getGroupUUIDs(self):
        return list(self.getGroups().values_list("uuid", flat=True))


class Member(User, RestModel, MetaDataModel):
    class RestMeta:
        NO_SHOW_FIELDS = ["password", "auth_code", "security_token"]
        SEARCH_FIELDS = ["username", "email", "first_name", "last_name", "display_name"]
        VIEW_PERMS = ["view_members", "manage_members", "manage_users", "owner"]
        SAVE_PERMS = ["invite_members", "manage_members", "manage_users", "owner"]
        LIST_DEFAULT_FILTERS = {
            "is_active": True
        }
        # note the | will check collection parameter...
        #   trailing "." will check if the collection has the key set to true
        SEARCH_TERMS = [
            "username", "email",
            "first_name", "last_name",
            "last_activity#datetime", "date_joined#datetime",
            "is_staff",
            ("notify_via", "properties|notify_via"),
            ("phone", "phone_number"),
            ("perms", "properties|permissions.")]
        UNIQUE_LOOKUP = ["username", "email"]
        METADATA_FIELD_PROPERTIES = getattr(settings, "USER_METADATA_PROPERTIES", None)
        GRAPHS = {
            "basic": {
                "fields": [
                    'id',
                    ('get_full_name', 'full_name'),
                    'first_name',
                    'last_name',
                    'display_name',
                    'initials',
                    'username',
                    'email',
                    'phone_number',
                    'last_login',
                    'last_activity',
                    'avatar'
                ]
            },
            "default": {
                "fields": [
                    'id',
                    'uuid',
                    'display_name',
                    ('get_full_name', 'full_name'),
                    'first_name',
                    'last_name',
                    'initials',
                    'username',
                    'email',
                    'phone_number',
                    'is_online',
                    'is_active',
                    'is_blocked',
                    'is_staff',
                    'is_superuser',
                    'requires_topt',
                    'last_login',
                    'last_activity',
                    ('date_joined', 'created'),
                    ("hasLoggedIn", "has_logged_in"),
                    'avatar',
                    'has_topt'
                ],
                "extra": ["metadata", "password_expires_in"],
            },
        }


    uuid = models.CharField(db_index=True, max_length=64, blank=True, default="")
    modified = models.DateTimeField(auto_now=True)

    phone_number = FormattedField(format=FormattedField.PHONE, default=None, null=True, max_length=64, db_index=True)
    display_name = models.CharField(max_length=64, blank=True, null=True, default=None)
    picture = models.ForeignKey("medialib.MediaItem", blank=True, null=True, help_text="Profile picture", related_name='+', on_delete=models.CASCADE)

    # we use this token to allow us to invalidate JWT tokens 
    security_token = models.CharField(max_length=64, blank=True, null=True, default=None, db_index=True)
    auth_code = models.CharField(max_length=64, blank=True, null=True, default=None, db_index=True)
    auth_code_expires = models.DateTimeField(blank=True, null=True, default=None)

    password_changed = models.DateTimeField(blank=True, null=True, default=None)
    last_activity = models.DateTimeField(blank=True, null=True, default=None)
    requires_topt = models.BooleanField(blank=True, null=True, default=False)

    def __str__(self):
        return self.username

    def getUser(self):
        return self.user_ptr

    def getGroup(self, group_id, include_parents=True):
        # now we want to verify we are a member of this group or a parent group
        if isinstance(group_id, str) and not group_id.isdigit():
            return None
        Group = RestModel.getModel("account", "Group")
        if self.hasPerm("view_all_groups"):
            return Group.objects.filter(pk=group_id).first()
        ms = self.getMembershipFor(group_id, include_parents)
        if ms is not None:
            if ms.group.id != group_id:
                # this means we got a parent ms, so lets turn the group itself
                return Group.objects.filter(pk=group_id).first()
            else:
                return ms.group
        return None

    @property
    def initials(self):
        if self.first_name and self.last_name:
            return "{}{}".format(self.first_name[0], self.last_name[0])
        return None

    @property
    def full_name(self):
        return self.get_full_name()

    @property
    def is_online(self):
        return self.getActiveConnections()

    @property
    def is_blocked(self):
        when = RemoteEvents.hget("users:blocked:username", self.username)
        if not when:
            return False
        # check if still blocked
        now = time.time()
        if now - float(when) > settings.LOCK_TIME:
            self.unblock()
            return False
        return True

    @property
    def has_topt(self):
        token = self.getProperty("totp_token", category="secrets", default=None)
        return token is not None

    @property
    def password_expires_in(self):
        # this is returned in hours
        if self.password_changed is None:
            self.password_changed = datetime.now()
            self.save()
        days = (datetime.now() - self.password_changed).days
        return settings.PASSWORD_EXPIRES_DAYS - days

    @property
    def avatar(self):
        if self.picture:
            return self.picture.thumbnail_url()
        return None

    def set_avatar(self, value):
        self.saveMediaFile(value, "picture", None, True)

    def hasLoggedIn(self):
        if not self.last_login or not self.date_joined:
            return False

        if (self.last_login - self.date_joined).total_seconds() > 2:
            return self.has_usable_password()
        return False

    def recordFailedLogin(self, request):
        c = RemoteEvents.hincrby("users:failed:username", self.username, 1)
        if c >= settings.LOCK_PASSWORD_ATTEMPTS:
            self.block("multiple incorrect password attempts", request=request)
        c = RemoteEvents.hincrby("users:failed:ip", request.ip, 1)

    def recordSuccessLogin(self, request):
        self.last_login = datetime.now()
        self.save()
        RemoteEvents.hdel("users:failed:username", self.username)
        RemoteEvents.hdel("users:failed:ip", request.ip)

    def hasPasswordExpired(self):
        now = datetime.now()
        if self.password_changed is None:
            self.password_changed = now
            self.save()
        return now - self.password_changed > timedelta(days=settings.PASSWORD_EXPIRES_DAYS)

    def login(self, password=None, request=None, use_jwt=False):
        if not self.is_active or self.is_blocked:
            return False
        # can force login
        if not request:
            request = rest_helpers.getActiveRequest()
        if password:
            if not self.checkPassword(password):
                # invalid password
                self.recordFailedLogin(request)
                return False
            else:
                self.recordSuccessLogin(request)
        if use_jwt:
            self.recordSuccessLogin(request)
            self.locateByIP(request.ip)
            return True
        self.user_ptr.backend = 'django.contrib.auth.backends.ModelBackend'
        auth_login(request, self.user_ptr)
        self.locateByIP(request.ip)
        return True

    def canLogin(self, request=None, throw_exception=True):
        if not self.is_active:
            self.log("login_blocked", F"account is not active {self.username}", request, method="login", level=31)
            if throw_exception:
                raise PermisionDeniedException("Account disabled", 410)
            return False
        if self.is_blocked:
            self.log("login_blocked", F"account is locked out {self.username}", request, method="login", level=31)
            if throw_exception:
                raise PermisionDeniedException("Account locked out", 411)
            return False
        if self.hasPasswordExpired():
            self.log("login_blocked", "password has expired", request, method="login", level=31)
            if throw_exception:
                raise PermisionDeniedException("password expired", 412)
            return False
        return True

    def touchActivity(self, force=False, last_login=False):
        is_dirty = False
        update_last_activity = datetime.now() - timedelta(minutes=5)
        if force or not self.last_activity or (self.last_activity and self.last_activity < update_last_activity):
            self.last_activity = datetime.now()
            is_dirty = True
        if last_login:
            update_last_login = datetime.now() - timedelta(hours=1)
            if not self.last_login or (self.last_login and self.last_login < update_last_login):
                self.last_login = datetime.now()
                self.last_activity = self.last_login
                is_dirty = True
        if is_dirty:
            self.save()

    def addPermission(self, perm):
        self.setProperty(perm, 1, "permissions")

    def removePermission(self, perm):
        self.setProperty(perm, None, "permissions")

    def hasPermission(self, perm):
        return self.hasPerm(perm)

    def hasPerm(self, perm):
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        if isinstance(perm, list):
            for i in perm:
                if self.hasPerm(i):
                    return True
            return False
        return self.getProperty(perm, 0, "permissions", bool)

    def hasGroupPerm(self, group, perm):
        if group is None:
            return False
        ms = self.getMembershipFor(group)
        if ms is None or ms.state < -10:
            return False
        return ms.hasPerm(perm)

    def checkPassword(self, raw_password):
        """
        Return a boolean of whether the raw_password was correct. Handles
        hashing formats behind the scenes.
        """
        def setter(raw_password):
            super(Member, self).set_password(raw_password)
            # Password hash upgrades shouldn't be considered password changes.
            self._password = None
            self.save(update_fields=["password"])
        return check_password(raw_password, self.password, setter)

    def _setPassword(self, value):
        super(Member, self).set_password(value)
        self.save()

    def setPassword(self, value, skip_history=False):
        """
        if (this.length > 6) score++;
        if (this.length > 11) score++;
        if (this.length > 15) score++;

        //if this has both lower and uppercase characters give 1 point
        if ( ( this.match(/[a-z]/) ) && ( this.match(/[A-Z]/) ) ) score++;

        //if this has at least one number give 1 point
        if (this.match(/\d+/)) score++;

        //if this has at least one special caracther give 1 point
        if ( this.match(/[!@#$%^&*.]/) ) score++;

        """
        score = 0
        score += 1 if len(value) > 6 else 0
        score += 1 if len(value) > 8 else 0
        score += 2 if len(value) > 15 else 0
        score += 1 if re.match(r'.*[a-z]', value) and re.match(r'.*[A-Z]', value) else 0
        score += 1 if re.match(r'.*\d+', value) else 0
        score += 1 if re.match(r'.*[!@#$%^&*.]', value) else 0
        if score < 3:
            self.log("password_error", "password is weak or duplicate", method="password_change", level=21)
            raise RestValidationError("password is weak or duplicate")
        if not skip_history and hasattr(settings, "PASSWORD_HISTORY") and settings.PASSWORD_HISTORY:
            hashed_password = PasswordHistory.HashPassword(value)
            # this means you can never reuse the same password
            if self.password_history.filter(password=hashed_password).count():
                self.log("password_error", "password already used", method="password_change", level=21)
                raise RestValidationError("password already used")
            if not self.id:
                self.save()
            PasswordHistory(owner=self, password=hashed_password).save()
        # self.set_password(value)
        self._setPassword(value)
        self.password_changed = datetime.now()
        self.save()
        self.log("password_changed", "password changed", method="password_change", level=21)
        return True

    def sendEvent(self, name, message, custom=None):
        if not custom:
            custom = {}
        custom["pk"] = self.id
        custom["member_id"] = self.id
        RemoteEvents.sendToUser(
            self,
            name,
            message=message,
            custom=custom)

    def sendChangeEvent(self, component, component_id, name="user.change", custom=None):
        if not custom:
            custom = {}
        custom["pk"] = self.id
        custom["member_id"] = self.id
        RemoteEvents.sendToUser(
            self,
            name,
            component=component,
            component_id=component_id,
            custom=custom)

    def isMemberOf(self, group, include_parents=True):
        ms = self.getMembershipFor(group, include_parents)
        return ms is not None

    def getMembershipFor(self, group, include_parents=True):
        # django should auto filter by group_id if int
        if group is None:
            return None
        if include_parents:
            qset = self.memberships.filter(Q(group=group) | Q(group__parent=group) | Q(group__children=group))
            if qset is not None:
                # the order of the above query is not logical, so we must do it ourselves
                # there is most likely only a few groups in this list
                # if we have a ms in the desired group lets return that
                # this logic should be less hard on db
                group_id = group
                if not isinstance(group_id, (int, str)):
                    group_id = group.id
                for ms in qset:
                    if ms.group_id == group_id:
                        return ms
                return qset.first()
            # now check by children
        return self.memberships.filter(group=group)

    def disable(self, by, reason="", notify=True):
        self.is_active = False
        self.save()
        self.memberships.update(state=-100)

        [s.delete() for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == self.pk]
        # notify account disabled
        subject = "MEMBER {} DISABLED BY {}".format(self, by)
        accounts = []
        body = "{}<br>\ndisabled from: ".format(reason)
        for m in self.memberships.all():
            accounts.append(m.group.name)
        body += "<br>\n".join(accounts)
        self.log("disabled", "account({}) disabled by {}, {}".format(self.username, by.username, reason), method="disabled", level=35)
        if notify:
            Member.notifyWithPermission("user_audit", subject, message=body, email_only=True)

    def enable(self, by, memberships=None):
        if not self.is_active:
            self.is_active = True
            self.save()
        # notify account disabled
        subject = "MEMBER {} RE-ENABLED BY {}".format(self, by)
        body = "enabled for: "
        if memberships is None:
            memberships = self.memberships.all()

        accounts = []
        for m in memberships:
            m.state = 10
            m.save()
            accounts.append(m.group.name)
        body += "<br>\n".join(accounts)
        self.log("enabled", "account enabled by {}".format(by.username), method="enabled", level=35)
        Member.notifyWithPermission("user_audit", subject, message=body, email_only=True)

    def locateByIP(self, ip):
        loc = GeoIP.get(ip)
        if loc is not None:
            self.setProperty("city", loc.city, "location")
            self.setProperty("state", loc.state, "location")
            self.setProperty("country", loc.country, "location")
            self.setProperty("lat", loc.lat, "location")
            self.setProperty("lng", loc.lng, "location")

    def sendSMS(self, msg):
        from telephony.models import SMS
        phone = self.getProperty("phone")
        if not phone or len(phone) < 7:
            return False
        SMS.send(phone, msg)
        return True

    def sendEmail(self, subject, body, attachments=[], do_async=True, template=None, context=None):
        rest_mail.send(
            self.email, subject, body, attachments=attachments,
            do_async=do_async, template=template, context=context)

    def sendInvite(self, subject, group=None, url=None, msg=None, **kwargs):
        context = rest_helpers.getContext(
            self.getActiveRequest(),
            member=self,
            group=group,
            url=url,
            msg=msg, **kwargs)
        rest_mail.send(self.email, subject, template="email/invite.html", context=context)

    def getActiveSessions(self):
        return SessionLog.objects.filter(user__id=self.pk, is_closed=False)

    def getSessionCount(self):
        return self.getActiveSessions().count()

    def logout(self, request=None, all_sessions=False, older_then=None):
        if not request:
            request = rest_helpers.getActiveRequest()

        if request and request.member == self:
            self.log("logout", "user logged out", request, method="logout", level=18)
            auth_logout(request)

        # else:
        #     qset = self.getActiveSessions()
        #     if older_then:
        #         age = datetime.now() - timedelta(days=older_then)
        #         qset = qset.filter(created__lte=age)
        #     for slog in qset:
        #         slog.logout()

    def notify(self, template=None, context=None, subject=None, message=None, email_only=True, sms_msg=None, force=False, from_email=settings.DEFAULT_FROM_EMAIL):
        from telephony.models import SMS
        # do not allow if account is not active
        if not self.is_active and not force:
            return False
        via = self.getProperty("notify_via", "all")
        phone = self.getProperty("phone")
        email = self.email
        valid_email = email is not None and "@" in email and "invalid" not in email
        allow_sms = not email_only and phone and (force or via in ["all", "sms"])
        allow_email = valid_email and (force or via in ["all", "email"])
        if not allow_email and not allow_sms:
            return False

        if allow_email:
            ctx = {
                'to': self.email,
                'to_token': crypto.hashit(self.email),
                'from': from_email,
                'timezone': "America/Los_Angeles"
            }

            if context:
                subject = context.get("subject", subject)
                message = context.get("message", message)
                ctx.update(context)

            from_email = ctx.get("from", None)
            rest_mail.send(
                [self.email],
                subject,
                message,
                from_email=from_email,
                template=template,
                context=ctx,
                do_async=True
            )
            self.log("notified", subject, method=self.email)

        if allow_sms:
            if not sms_msg and subject:
                sms_msg = subject
            if not sms_msg and message:
                sms_msg = message
            SMS.send(phone, sms_msg)
            self.log("notified", subject, method=phone)
        return True

    def checkIsOwner(self, member):
        return self.id == member.id

    def canSee(self, user):
        if user.id == self.id or self.hasPerm(["manage_members", "view_members"]):
            return True
        return False

    def canEdit(self, user, allow_self_edit=True):
        if allow_self_edit and user.id == self.id:
            return True
        if user.is_staff:
            # only super user can edit staff users
            return self.is_superuser or self.hasPerm("manage_staff")
        if self.hasPerm(["manage_users", "manage_staff"]):
            return True
        # we need to find any groups these users have in common
        # then find if the request.member is a manager or hasPerm admin or manager
        common_groups = user.getGroups().filter(memberships__member=self)
        if common_groups.count():
            # we have some common groups lets see if self is a admin or manager
            qset = self.memberships.filter(group__in=common_groups).filter(Q(permissions__name__in=["admin", "manager", "manage_members"])|Q(role__icontains="manager"))
            return qset.count() > 0
        return False

    def canEditMe(self, user):
        return user.canEdit(self)

    def refreshSecurityToken(self):
        self.security_token = crypto.randomString(8)
        self.save()

    def generateAuthCode(self, length=6, expires=AUTH_CODE_EXPIRES_SECS):
        for i in range(0, 100):
            code = crypto.randomCode(length)
            if Member.objects.filter(auth_code=code).count() == 0:
                self.auth_code = code
                self.auth_code_expires = datetime.now() + timedelta(seconds=expires)
                self.save()
                return self.auth_code
        return None

    # time based one time passwords / GOOGLE Authenticator
    def totp_getSecret(self, reset=False):
        token = self.getProperty("totp_token", category="secrets", default=None)
        if token is None or reset:
            token = pyotp.random_base32()
            self.setProperty("totp_token", token, category="secrets")
        return token

    def totp_getURI(self):
        # this should only be used one time during setup
        token = self.totp_getSecret(reset=True)
        totp = pyotp.TOTP(token)
        return totp.provisioning_uri(name=self.username, issuer_name=settings.SITE_LABEL)

    def totp_verify(self, code, window=1):
        token = self.totp_getSecret()
        totp = pyotp.TOTP(token)
        return totp.verify(code, valid_window=window)

    def block(self, reason, request=None):
        if not request:
            request = self.getActiveRequest()
        PersistentLog.log("account blocked, {}".format(reason), 5, request, "account.Member", self.pk, "blocked")
        RemoteEvents.hset("users:blocked:username", self.username, time.time())

    def unblock(self, request=None):
        if not request:
            request = self.getActiveRequest()
        if request and request.user.is_authenticated:
            who = request.user.username
        else:
            who = "time"
        PersistentLog.log("account unblocked by {}".format(who), 5, request, "account.Member", self.pk, "unblocked")
        RemoteEvents.hdel("users:blocked:username", self.username)
        RemoteEvents.hdel("users:failed:username", self.username)

    def getActiveConnections(self):
        c = RemoteEvents.hget("member:online:connections", self.id)
        if c:
            return int(c)
        return 0

    # BEGIN REST CALLBACKS
    def on_permission_change(self, key, value, old_value, category):
        # called when a metadata.permissions field changes.. see django settings USER_METADATA_PROPERTIES 
        # we want to log both the person changing permissions
        # and those being changed
        request = RestModel.getActiveRequest()
        perm = key
        reason = ""

        if "reason" in request.DATA:
            reason = request.DATA.get("reason").strip()

        if request.member:
            if value in [None, 0, '0']:
                self.log("remove_perm", "{} removed perm {}; {}".format(request.user.username, perm, reason), method="permissions", level=10)
                request.member.log("removed_perm", "removed perm {} for {}; {}".format(perm, self.username, reason), method="permissions", level=10)
            else:
                self.log("add_perm", "{} added perm {}; {}".format(request.user.username, perm, reason), method="permissions", level=10)
                request.member.log("gave_perm", "gave perm {} for {}; ".format(perm, self.username, reason), method="permissions", level=10)
        else:
            if value in [None, 0, '0']:
                self.log("remove_perm", "system removed perm {}".format(perm), method="permissions", level=10)
            else:
                self.log("add_perm", "system added perm {}".format(perm), method="permissions", level=10)

    def set_is_staff(self, value):
        request = self.getActiveRequest()
        if not request.member.hasPermission("manage_staff"):
            raise PermisionDeniedException("Permission Denied: attempting to set staff user")
        self.is_staff = int(value)

    def set_disable(self, value):
        if value is not None and value in [1, '1', True, 'true']:
            self.set_action("enable")
        self.set_action("disable")

    def set_action(self, value):
        action = value
        request = self.getActiveRequest()
        if action in ["unlock", "unblock"]:
            if not request.member.is_staff and not self.canEditMe(request.member):
                raise PermisionDeniedException("Permission Denied: attempting to unlock user")
            self.unblock(request)
        elif action == "disable":
            if self.is_superuser and not request.user.is_superuser:
                raise PermisionDeniedException("Permission Denied: attempting to disable super user")
            if self.is_staff and not request.member.is_staff:
                raise PermisionDeniedException("Permission Denied: attempting to disable staff user")
            if not request.member.is_staff and not self.canEditMe(request.member):
                raise PermisionDeniedException("Permission Denied: attempting to dsiable user")
            self.disable(request.user)
        elif action == "enable":
            if not request.member.is_staff and not self.canEditMe(request.member):
                raise PermisionDeniedException("Permission Denied: attempting to enable user")
            self.enable(request.member)
        elif action == "touch_password":
            if not request.member.is_staff and not self.canEditMe(request.member):
                raise PermisionDeniedException("Permission Denied: attempting to touch password")
            self.password_changed = datetime.now()
            self.save()
        elif action == "update_password_next":
            # force the user to update password on next login
            if not request.member.is_staff and not self.canEditMe(request.member):
                raise PermisionDeniedException("Permission Denied: attempting to touch password")
            self.password_changed = datetime.now() - timedelta(days=settings.PASSWORD_EXPIRES_DAYS - 1)
            self.save()

    def set_full_name(self, value):
        self.set_name(value)

    def set_name(self, value):
        if not value:
            return
        print(("setting name: {0}".format(value)))
        names = value.split(' ')
        self.first_name = names[0].title()
        if len(names) > 1:
            self.last_name = " ".join(names[1:]).title()
        self.display_name = value.title()

    def set_username(self, value, generate=True):
        # we force our usernames to be the sames as the email
        value = value.lower()
        value = value.replace(' ', '.')
        if '@' in value:
            uname = self.username
            self.username = None
            self.set_email(value)
            if self.username is None:
                self.username = uname
        elif self.username != value:
            orig_value = value
            if generate:
                for i in range(0, 20):
                    if Member.verifyUsername(value, self.id):
                        self.username = value
                        return True
                    value = "{}{}".format(orig_value, i)
            else:
                if Member.verifyUsername(value, self.id):
                    self.username = value
                    return True
            raise RestValidationError("username '{}'' already exists!".format(value))

    def set_newpassword(self, value):
        request = self.getActiveRequest()
        if not request:
            raise RestValidationError("requires request to continue")
        old_password = request.DATA.get("oldpassword", None)
        if not old_password:
            request.member.log("password_error", "requires oldpassword to change password", method="password_change", level=10)
            raise RestValidationError("requires oldpassword to continue")
        # verify we have the old password correct
        if not self.checkPassword(old_password):
            # invalid password
            request.member.log("password_error", "incorrect oldpassword to change password", method="password_change", level=10)
            raise RestValidationError("old password is not correct")
        self.set_password(value)

    def set_password(self, value):
        """
        this is tricky because we need to call set_password on the User model
        """
        request = self.getActiveRequest()
        if not request.member.canEdit(self):
            request.member.log("permission_denied", "attempting to set password for user: {}".format(self.username), method="password_change", level=3)
            raise PermisionDeniedException("Permission Denied: attempting to change password")
        if request.member.id != self.id:
            self.log("modified_by", "password changed by: {}".format(request.member.username), method="password_change", level=31)
            request.member.log("member_edit", "{} password changed".format(self.username), method="password_change", level=31)
            self.setPassword(value, skip_history=True)
        else:
            self.setPassword(value)

    def set_email(self, value):
        # we force our usernames to be the sames as the email
        # basic validation
        if value is not None:
            value = value.lower()

        if self.email == value:
            return

        if "@" not in value or "." not in value:
            raise RestValidationError("Invalid Email")

        # verify there is not another account with this email
        qs = Member.objects.filter(email=value)
        if self.id:
            qs.exclude(pk=self.id)
        if qs.count():
            raise RestValidationError("user with email {} already exists!".format(value))

        if self.email:
            self.log("email_changed", "email changed from {} to {}".format(self.email, value), method="email_change", level=7)
        self.email = value

        if self.username:
            if "@" in self.username:
                if Member.verifyUsername(value, self.id):
                    self.username = value
            return True

        if len(value) > 250:
            value = value.split("@")[0]
        if Member.verifyUsername(value, self.id):
            self.username = value
        else:
            raise RestValidationError("email to username '{}' already exists!".format(value))

    def set_invite_body(self, value):
        # this is called typically for a system level user
        if value:
            subject = "Invite Link"
            request = self.getActiveRequest()
            if request is not None:
                subject = request.DATA.get("invite_subject", subject)
            self.sendEmail(subject, value)

    def on_rest_can_get(self, request):
        if request.member.pk == self.pk:
            return True
        return super().on_rest_can_get(request)

    def on_rest_can_save(self, request):
        if request.member.pk == self.pk:
            return True
        return super().on_rest_can_save(request)

    def on_rest_created(self, request):
        self.uuid = Member.generateUUID(self.pk)
        if not self.display_name:
            if self.full_name:
                self.display_name = self.full_name
            else:
                self.display_name = self.username
        self.save()

    # BEGIN STATIC METHODS
    @staticmethod
    def getByUser(user):
        member = Member.objects.filter(pk=user.pk).first()
        if member is None:
            member = Member(user_ptr=user)
            for f in user._meta.local_fields: setattr(member, f.name, getattr(user, f.name))
            member.save()
        return member

    @staticmethod
    def RecordInvalidLogin(request, username=None):
        # this records events when a username doesn't even exist
        if not username:
            username = request.DATA.get("username", None)
        if username:
            RemoteEvents.hset("users:failed:username", username, 0)

    @staticmethod
    def verifyUsername(username, exclude=None):
        qs = Member.objects.filter(username=username)
        if exclude:
            qs.exclude(pk=exclude)
        return qs.count() == 0

    @staticmethod
    def GetMember(username):
        if "@" in username:
            m = Member.objects.filter(email=username.lower()).last()
            if m:
                return m
        return Member.objects.filter(username=username.lower()).last()

    @staticmethod
    def GetMemberByPhone(phone_number):
        return Member.objects.filter(phone_number=phone_number.lower()).last()

    @staticmethod
    def GetWithPermission(perm, email_list=False):
        if type(perm) is list:
            queries = [Q(properties__category="permissions", properties__key=p, properties__value="1") for p in perm]
            query = queries.pop()
            for item in queries:
                query |= item
            qset = Member.objects.filter(is_active=True).filter(query).distinct()
        else:
            qset = Member.objects.filter(is_active=True).filter(properties__category="permissions", properties__key=perm, properties__value="1")

        if email_list:
            return list(qset.exclude(email__icontains="invalid").values_list('email', flat=True))
        return qset

    @staticmethod
    def FilterOnline(is_online, qset):
        ids = list(RemoteEvents.smembers("member:online"))
        if is_online:
            qset = qset.filter(pk__in=ids)
        else:
            qset = qset.exclude(pk__in=ids)
        return qset

    @staticmethod
    def FilterBlocked(is_blocked, qset):
        ids = list(RemoteEvents.hgetall("users:blocked:username"))
        if is_blocked:
            qset = qset.filter(username__in=ids)
        else:
            qset = qset.exclude(username__in=ids)
        return qset

    @staticmethod
    def notifyWithPermission(perm, subject, message=None, template=None, context=None, email_only=False, sms_msg=None, force=False):
        NotificationRecord = RestModel.getModel("account", "NotificationRecord")
        NotificationRecord.notify(Member.GetWithPermission(perm), subject, message, template, context, email_only, sms_msg, force)

    @classmethod
    def authWS4RedisConnection(cls, auth_data):
        """
        This method is used by the async/websocket service to authenticate.
        If the model can authenticate the connection it should return dict 
        with kind and pk of the model that is authenticaed
        """

        # assume this is a session key
        # this is deprecated, only using for backwards
        from importlib import import_module
        from rest import UberDict
        # engine = import_module(settings.SESSION_ENGINE)
        # SessionStore = engine.SessionStore
        # session = SessionStore(auth_data.token)
        session = Session.objects.filter(session_key=auth_data.token).last()
        if session is None:
            rest_helpers.log_print("no session for key", auth_data)
            return None
        session_data = session.get_decoded()
        rest_helpers.log_print(session_data)
        uid = session_data.get('_auth_user_id')
        member = cls.objects.filter(pk=uid).last()
        if member is not None:
            return UberDict(kind="member", pk=uid, member=member)
        return None


class MemberMetaData(MetaDataBase):
    parent = models.ForeignKey(Member, related_name="properties", on_delete=models.CASCADE)


# class MemberPermission(models.Model):
#     member = models.ForeignKey(Member, related_name="permissions", on_delete=models.CASCADE)
#     name = models.CharField(max_length=255, db_index=True)


class PasswordHistory(models.Model):
    created = models.DateTimeField(auto_now_add=True, editable=False)
    owner = models.ForeignKey(Member, related_name="password_history", on_delete=models.CASCADE)
    password = models.CharField(max_length=255)

    @staticmethod
    def HashPassword(password):
        return hashlib.sha512((settings.SECRET_KEY + password).encode('utf-8')).hexdigest()


class AuthToken(models.Model, RestModel):
    class RestMeta:
        NO_SHOW_FIELDS = ["token"]
        CAN_DELETE = True
        SEARCH_FIELDS = ["member__username", "member__email", "member__first_name", "member__last_name"]
        GRAPHS = {
            "default": {
                "extra": ["secure_token"],
                "graphs": {
                    "member": "simple"
                }
            },
            "list": {
                "extra": ["secure_token"],
                "graphs": {
                    "member": "simple"
                }
            }
        }
    created = models.DateTimeField(auto_now_add=True, editable=False)
    token = models.TextField(db_index=True, unique=True)
    member = models.ForeignKey(Member, related_name="auth_tokens", on_delete=models.CASCADE)
    role = models.CharField(max_length=128, null=True, default=None, blank=True)
    signature = models.CharField(max_length=128, null=True, default=None, blank=True, db_index=True)

    def generateToken(self, commit=True):
        self.token = str(uuid.uuid1())
        self.updateSignature()
        if commit:
            self.save()

    def updateSignature(self):
        self.signature = crypto.hashSHA256(self.token)

    def on_rest_pre_save(self, request, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
            self.updateSignature()
        if not self.member_id:
            self.member = request.member
        if not request.member.canEdit(self.member):
            raise PermisionDeniedException("user is not allowed to create auth token for user", 469)

    @property
    def secure_token(self):
        request = self.getActiveRequest()
        if request:
            if self.member == request.member or request.member.is_superuser:
                return self.token
            if len(self.token) > 6:
                return "{}{}".format("*" * (len(self.token)-4), self.token[-4:])
        return "{}{}".format("*" * (len(self.token)-4), self.token[-4:])

    def __str__(self):
        return "{o.member}: {o.secure_token}".format(o=self)


