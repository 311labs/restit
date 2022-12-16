from django.db import models

from rest import settings
from rest import models as rm
from rest import helpers as rest_helpers

from account.models import Member
from datetime import datetime, timedelta


class Bounce(models.Model, rm.RestModel):
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
    user = models.ForeignKey("account.Member", related_name="emails_bounced", null=True, blank=True, default=None, on_delete=models.CASCADE)
    address = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=32, db_index=True)
    reason = models.TextField(null=True, blank=True, default=None)
    reporter = models.CharField(max_length=255, null=True, blank=True, default=None)
    code = models.CharField(max_length=32, null=True, blank=True, default=None)
    source = models.CharField(max_length=255, null=True, blank=True, default=None)
    source_ip = models.CharField(max_length=64, null=True, blank=True, default=None)

    def __str__(self):
        return f"bounce: address:{self.address} reason:{self.reason}"

    @staticmethod
    def log(kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None):
        obj = Bounce(kind=kind, address=address)
        obj.reason = reason
        obj.reporter = reporter
        obj.code = code
        obj.source = source
        obj.source_ip = source_ip
        if user is None:
            user = Member.objects.filter(email=address).last()
            # now lets check our bounced count, if more then 3, we turn off email
            if user:
                user.log("bounced", "{} bounced to {} from {}".format(kind, address, source_ip), method=kind)
                since = datetime.now() - timedelta(days=14)
                bounce_count = Bounce.objects.filter(user=user, created__gte=since).count()
                if bounce_count > 2:
                    # TODO notify support an account has been disabled because of bounce
                    user.setProperty("notify_via", "off")
                    user.log("disabled", "notifications disabled because email bounced", method="notify")
        else:
            # TODO notify support of unknown bounce
            pass
        obj.user = user
        obj.save()
