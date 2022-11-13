
from django.db import models
from rest import models as rm
from objict import objict
from datetime import datetime

CM_BACKENDS = objict()


class MemberDevice(models.Model, rm.RestModel, rm.MetaDataModel):
    """
    MemberDevice Model tracks personal devices associated with a user.
    This can include mobile and desktop devices.
    """
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    member = models.ForeignKey("account.Member", related_name="devices", on_delete=models.CASCADE)

    name = models.CharField(max_length=128, blank=True, null=True, default=None)
    uuid = models.CharField(db_index=True, max_length=128, blank=True, null=True, default=None)

    cm_provider = models.CharField(db_index=True, max_length=64, default="fcm")
    cm_token = models.CharField(max_length=250, default=None, null=True)

    kind = models.CharField(db_index=True, max_length=64, default="unknown")
    state = models.IntegerField(db_index=True, default=1)

    class RestMeta:
        GRAPHS = {
            "default": {
                "extra": ["metadata"],
            }
        }

    def sendData(self, message, **kwargs):
        messenger = getCloudMessanger(self.cm_provider)
        if messenger:
            return messenger.sendToDevice(self, message)
        return objict(status_code=404, reason=self.cm_provider)

    def sendNotification(self, title, body):
        messenger = getCloudMessanger(self.cm_provider)
        if messenger:
            return messenger.sendNotification(self.cm_token, title, body)
        return objict(status_code=404, reason=self.cm_provider)

    def notify(self, title, body):
        return self.sendNotification(title, body)

    def touch(self):
        self.modified = datetime.now()
        self.save()

    @classmethod
    def sendMessageTo(cls, message, devices, **kwargs):
        pass

    @classmethod
    def register(cls, request, member, device_id):
        cm_token = request.DATA.get("cm_token")
        default_provider = "ws"
        if cm_token is not None:
            default_provider = "fcm"
        cm_provider = request.DATA.get("cm_provider", default=default_provider)
        md = MemberDevice.objects.filter(uuid=device_id, member=member).last()
        if md is not None:
            return md
        md = MemberDevice(uuid=device_id, member=member, cm_token=cm_token, cm_provider=cm_provider)
        md.name = F"{member.first_name} {request.auth_session.device}"
        md.kind = request.auth_session.os.lower()
        if md.kind.startswith("mac"):
            md.kind = "mac"
        md.save()
        md.setProperty("user_agent", request.META.get('HTTP_USER_AGENT', ''))
        return md


class MemberDeviceMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(MemberDevice, related_name="properties", on_delete=models.CASCADE)


def getCloudMessanger(name):
    if name not in CM_BACKENDS:
        if name == "fcm":
            from account import fcm
            CM_BACKENDS["fcm"] = fcm
    return CM_BACKENDS[name]

