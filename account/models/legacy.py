from django.db import models
from rest import models as rm
import uuid


# DEPRECATED!
class Permission(models.Model):
    membership = models.ForeignKey("account.Membership", related_name="permissions", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)


class AuthAccount(models.Model, rm.RestModel):
    class RestMeta:
        SEARCH_FIELDS = ["member__first_name", "member__last_name"]
        NO_SHOW_FIELDS = ["pin", "pan"]
        GRAPHS = {
            "default": {
                "graphs": {
                    "member": "basic",
                },
                "extra": [
                    "pan_last_4",
                ],
            },
            "list": {
                "graphs": {
                    "self": "default"
                }
            },
            "detailed": {
                "graphs": {
                    "self": "default"
                }
            }
        }

    created = models.DateTimeField(auto_now_add=True, editable=False)
    pan = models.TextField(db_index=True)
    pin = models.CharField(max_length=64, blank=True, null=True, default=None)
    kind = models.CharField(max_length=128, blank=True, null=True, default=None)
    member = models.ForeignKey("account.Member", related_name="auth_accounts", on_delete=models.CASCADE)
    state = models.IntegerField(default=1, choices=[(0, "disabled"), (1, "enabled")], db_index=True)

    @property
    def pan_last_4(self):
        if not self.pan:
            return ""
        return self.pan[-4:]

    def set_kind(self, kind):
        self.kind = kind
        if kind == "authtoken":
            request = self.getActiveRequest()
            if bool(request):
                pan = request.DATA.get("pan")
                if not pan or len(pan) < 8:
                    # do not let user set pans on auth tokens
                    self.pan = str(uuid.uuid1())
                    # override it in the data to make sure
                    request.DATA.set("pan", self.pan)

    @classmethod
    def queryFromRequest(cls, request, qset):
        if not request.user.is_staff:
            member_id = request.DATA.get(["member", "member_id"])
            if not member_id:
                member_id = request.member.id
            qset = qset.filter(member_id=member_id)
        return super(AuthAccount, cls).queryFromRequest(request, qset)

    @classmethod
    def on_rest_list_filter(cls, request, qset=None):
        if request.group:            
            members = request.group.getMembers(as_member=True, include_parents=False)
            qset = qset.filter(member__in=members)
        return qset

    def __unicode__(self):
        return "{o.member} <{o.pan}>".format(o=self)
