from django.db import models
from datetime import datetime

from rest.models import RestModel
from rest import ua


# replacing legacy cookie session system with more robust session info
class AuthSession(models.Model, RestModel):
    class RestMeta:
        SEARCH_FIELDS = ["ip", "member__username", "browser", "location__city"]
        VIEW_PERMS = ["view_members", "manage_members", "manage_users"]
        CAN_SAVE = False
        CAN_DELETE = False
        # note the | will check collection parameter...
        #   trailing "." will check if the collection has the key set to true
        SEARCH_TERMS = [
            "ip", "device", "browser", "os",
            ("username", "member__username"),
            ("email", "member__email"),
            ("first_name", "member__first_name"),
            ("last_name", "member__last_name"),
            "last_activity#datetime"]
        GRAPHS = {
            "default": {
                "graphs": {
                    "location": "default"
                }
            }
        }
    # the signature of session
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    last_activity = models.DateTimeField(db_index=True)

    signature = models.CharField(max_length=127, db_index=True)
    ip = models.CharField(max_length=127, null=True, blank=True, db_index=True)

    member = models.ForeignKey("account.Member", null=True, blank=True, related_name="auth_sessions", on_delete=models.CASCADE)
    location = models.ForeignKey("location.GeoIP", related_name="auth_sessions", blank=True, null=True, default=None, on_delete=models.CASCADE)

    user_agent = models.TextField(blank=True, null=True)
    browser = models.CharField(max_length=64, null=True, blank=True, default=None)
    os = models.CharField(max_length=64, null=True, blank=True, default=None)
    device = models.CharField(max_length=64, null=True, blank=True, default=None)

    def touch(self):
        self.last_activity = datetime.now()
        self.save()

    def updateLocation(self):
        if self.location is None and self.ip:
            GeoIP = self.getModel("location", "GeoIP")
            self.location = GeoIP.get(self.ip)
        return self.location

    def updateUA(self):
        if self.user_agent:
            ua_info = ua.parse(self.user_agent)
            self.browser = ua_info.get("user_agent.family")
            self.os = ua_info.get("os.family")
            self.device = ua_info.get("device.family")

    def __str__(self):
        return f"{self.member.username} - {self.ip} - {self.os} - {self.browser}"

    @classmethod
    def NewSession(cls, request):
        obj = cls(ip=request.ip, member=request.member, signature=request.signature)
        obj.user_agent = request.META.get('HTTP_USER_AGENT', None)
        obj.last_activity = datetime.now()
        obj.updateUA()
        obj.updateLocation()
        obj.save()
        return obj

    @classmethod
    def GetSession(cls, request, touch=True):
        if request.signature and request.member:
            session = AuthSession.objects.filter(signature=request.signature, member=request.member, ip=request.ip).last()
            if session is None:
                return cls.NewSession(request)
            if touch:
                session.touch()
            return session
        return None

