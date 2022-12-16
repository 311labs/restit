from django.db import models

from rest import settings
from rest import models as rm
from rest import helpers as rest_helpers

from account.models import Member
from datetime import datetime, timedelta


class Complaint(models.Model, rm.RestModel):
    class RestMeta:
        CAN_SAVE = CAN_CREATE = False
        DEFAULT_SORT = "-id"
        SEARCH_FIELDS = ["address"]
        SEARCH_TERMS = [
            ("email", "address"),
            ("to", "address"), "source", "reason", "state",
            ("user", "user__username")]
        
        GRAPHS = {
            "default": {
                "graphs": {
                    "user": "basic"
                }
            },
            "list": {
                "graphs": {
                    "user": "basic"
                }
            }
        }
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    user = models.ForeignKey("account.Member", related_name="emails_complaints", null=True, blank=True, default=None, on_delete=models.CASCADE)
    address = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=32, db_index=True)
    reason = models.TextField(null=True, blank=True, default=None)
    user_agent = models.CharField(max_length=255, null=True, blank=True, default=None)
    source = models.CharField(max_length=255, null=True, blank=True, default=None)
    source_ip = models.CharField(max_length=64, null=True, blank=True, default=None)

    def __str__(self):
        return f"complaint: address:{self.address} reason:{self.reason}"

    @staticmethod
    def log(kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None):
        obj = Complaint(kind=kind, address=address)
        obj.reason = reason
        obj.reporter = reporter
        obj.code = code
        obj.source = source
        obj.source_ip = source_ip
        if user is None:
            user = Member.objects.filter(email=address).last()
            # now if user has complaint we shut down right away
            if user:
                user.log("complaint", "{} complaint to {} from {}".format(kind, address, source_ip), method=kind)
                user.setProperty("notify_via", "off")
                user.log("disabled", "notifications disabled because email complaint", method="notify")
        else:
            # TODO notify support of unknown bounce
            pass
        obj.user = user
        obj.save()
