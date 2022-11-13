from django.db import models
from django.conf import settings

from django.template.loader import render_to_string
from rest.models import RestModel
from account.models import Group, Member
from . import phone_util


class SMS(models.Model, RestModel):
    class RestMeta:
        CAN_CREATE = False
        DEFAULT_SORT = "-created"
        QUERY_FIELDS = ["endpoint", "srcpoint"]
        SEARCH_FIELDS = ["endpoint", "srcpoint"]
        SEARCH_TERMS = [
            ("phone", "endpoint"),
            ("to", "endpoint"),
            ("from", "srcpoint")]
        FILTER_FIELDS = ["state", "created", "owner", "group"]
        GRAPHS = {
            "basic": {
                "graphs": {
                    "by": "basic",
                    "to": "basic"
                }
            },

            "default": {
                "graphs": {
                    "self": "basic",
                }
            },

            "detailed": {
                "extra": ["number_info"],
                "graphs": {
                    "by": "basic",
                    "to": "basic"
                }
            }
        }

    sid = models.CharField(max_length=125, blank=True, null=True, default=None)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    group = models.ForeignKey(Group, related_name="telephony_sms", blank=True, null=True, default=None, on_delete=models.CASCADE)
    by = models.ForeignKey(Member, related_name="telephony_sms_out", blank=True, null=True, default=None, on_delete=models.CASCADE)
    to = models.ForeignKey(Member, related_name="telephony_sms_in", blank=True, null=True, default=None, on_delete=models.CASCADE)
    # the mechanism , sms, push, etc
    transport = models.CharField(max_length=125, blank=True, null=True, default=None)
    # this can be email, phone, etc
    endpoint = models.CharField(max_length=200, blank=True, null=True, default=None, db_index=True)
    # this can be email, phone, etc
    srcpoint = models.CharField(max_length=200, blank=True, null=True, default=None)

    # direction of message
    is_inbound = models.BooleanField(default=False)

    status = models.CharField(max_length=64, default=None, null=True, db_index=True)
    reason = models.TextField(default=None, null=True)

    message = models.TextField()

    @property
    def number_info(self):
        if self.is_inbound:
            return PhonenumberInfo.lookup(self.srcpoint)
        return PhonenumberInfo.lookup(self.endpoint)

    @staticmethod
    def log_incoming(request):
        """
        {
            "AccountSid": "ACb27c3a393ddca77bc32f0757c98b1a59",
            "ApiVersion": "2010-04-01",
            "Body": "Testing",
            "From": "+19496065381",
            "FromCity": "LAGUNA NIGUEL",
            "FromCountry": "US",
            "FromState": "CA",
            "FromZip": "92692",
            "MessageSid": "SM53f8730fa9bf22ccaf51d3ec8bd87fa9",
            "NumMedia": "0",
            "NumSegments": "1",
            "SmsMessageSid": "SM53f8730fa9bf22ccaf51d3ec8bd87fa9",
            "SmsSid": "SM53f8730fa9bf22ccaf51d3ec8bd87fa9",
            "SmsStatus": "received",
            "To": "+19493157900",
            "ToCity": "LAGUNA BEACH",
            "ToCountry": "US",
            "ToState": "CA",
            "ToZip": "92656"
        }
        """
        msg = SMS(endpoint=request.DATA.get("To"),
            message=request.DATA.get("Body"),
            srcpoint=request.DATA.get("From"),
            transport="sms", is_inbound=True)
        msg.sid = request.DATA.get("MessageSid")
        msg.status = request.DATA.get("SmsStatus")
        msg.save()
        return None

    @staticmethod
    def normalizePhone(phonenum):
        return phone_util.normalize(phonenum)

    @staticmethod
    def broadcast(to, message, by=None, group=None, transport="sms", srcpoint=None):
        if srcpoint is None:
            srcpoint = settings.TELEPHONY_DEFAULT_SRC

        srcpoint = phone_util.normalize(srcpoint)
        msg = None
        for t in to:
            to_num = t.getProperty("phone")
            if to_num and len(to_num) > 4:
                SMS.send(to_num, message, by=by, group=group, transport=transport, srcpoint=srcpoint)
        return msg

    @staticmethod
    def sendTemplate(endpoint, template, context, by=None, group=None, to=None, transport="sms", srcpoint=None):
        message = render_to_string(template, context)
        return SMS.send(endpoint, message, by, group, to, transport, srcpoint)

    @staticmethod
    def send(endpoint, message, by=None, group=None, to=None, transport="sms", srcpoint=None, verify=True):
        if srcpoint is None:
            srcpoint = settings.TELEPHONY_DEFAULT_SRC

        # format the to srcpoint
        if endpoint.startswith("555") or endpoint.startswith("+1 555"):
            # HACK: send sms to ians work phone
            endpoint = settings.TELEPHONY_555_TO

        endpoint = phone_util.normalize(endpoint)
        srcpoint = phone_util.normalize(srcpoint)
        if verify:
            to_info = PhonenumberInfo.lookup(endpoint)
            if not to_info.sms_allowed:
                msg = SMS(endpoint=endpoint, message=message, srcpoint=srcpoint, transport=transport, by=by, to=to, group=group)
                msg.status = "send failed"
                msg.reason = "number valid: {} number kind: {} cannot receive sms".format(to_info.is_valid, to_info.kind)
                msg.save()
                return msg
        resp = phone_util.sendSMS(endpoint, srcpoint, message)
        msg = SMS(endpoint=endpoint, message=message, srcpoint=srcpoint, transport=transport, by=by, to=to, group=group)
        msg.sid = resp.sid
        msg.status = resp.status
        msg.reason = resp.error_message
        msg.save()
        return msg


class PhonenumberInfo(models.Model, RestModel):
    class RestMeta:
        CAN_CREATE = False
        QUERY_FIELDS = ["number", "owner_name"]
        SEARCH_FIELDS = ["number", "owner_name"]
        SEARCH_TERMS = [
            ("phone", "number"),
            ("name", "owner_name"),
            ("kind", "kind")]

    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True)
    number = models.CharField(max_length=200, db_index=True)
    owner_name = models.CharField(max_length=200, default=None, null=True)
    owner_kind = models.CharField(max_length=200, default=None, null=True)
    country = models.CharField(max_length=64, default=None, null=True)
    carrier_name = models.CharField(max_length=64, default=None, null=True)
    kind = models.CharField(max_length=64, default=None, null=True)
    is_valid = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    sms_allowed = models.BooleanField(default=False)

    def refresh(self):
        resp = phone_util.lookup(self.number)
        if resp.success:
            self.owner_name = resp.owner_name
            self.owner_kind = resp.owner_kind
            if resp.carrier:
                self.carrier_name = resp.carrier.name
                self.kind = resp.carrier.type
            self.is_valid = self.owner_kind is not None
            self.sms_allowed = self.kind in ["mobile", "voip"]
        self.save()

    @staticmethod
    def lookup(number, country="US"):
        number = phone_util.normalize(number, country)
        info = PhonenumberInfo.objects.filter(number=number).last()
        if info is None:
            info = PhonenumberInfo(number=number)
            if phone_util.isValid(number):
                info.refresh()
        return info

    @staticmethod
    def normalize(number, country="US"):
        return phone_util.normalize(number, country)


