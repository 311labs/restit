from django.db import models
from rest import models as rm
from rest.encryption import DECRYPTER, ENCRYPTER
from rest import UberDict

SETTINGS_CACHE = UberDict()


class Settings(models.Model, rm.RestModel, rm.MetaDataModel):
    """
    Create collection of settings.
    This is very useful for create special blocks of settings.
    """
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    name = models.CharField(max_length=128, unique=True)

    owner = models.ForeignKey(
        "account.Member", related_name="settings",
        null=True, default=None, on_delete=models.CASCADE)
    group = models.ForeignKey(
        "account.Group", related_name="settings",
        null=True, default=None, on_delete=models.CASCADE)

    class RestMeta:
        GRAPHS = {
            "default": {
                "extra": ["metadata"],
            }
        }


class SettingsMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(Settings, related_name="properties", on_delete=models.CASCADE)


def setSetting(name, key, value, encrypt=False):
    obj = Settings.objects.filter(name=name).last()
    if obj is None:
        obj = Settings(name=name)
        obj.save()
    if encrypt:
        value = ENCRYPTER.encrypt(value)
    obj.setProperty(key, value)
    SETTINGS_CACHE[name] = UberDict.fromdict(obj.metadata())


def getSetting(name, key, decrypt=False, cache=True):
    settings = getSettingsDict(name)
    if settings is None:
        return None
    if not decrypt:
        return settings.get(key, None)

    value = settings.get(f"decrypted.{key}", None)
    if value is None:
        return value

    value = DECRYPTER.decrypt(value)
    if cache:
        settings.set(f"decrypted.{key}", value)
    return value


def getSettings(name):
    return Settings.objects.filter(name=name).last()


def getSettingsDict(name, refresh=False):
    if refresh or name not in SETTINGS_CACHE:
        obj = Settings.objects.filter(name=name).last()
        if obj:
            SETTINGS_CACHE[name] = UberDict.fromdict(obj.metadata())
    return SETTINGS_CACHE.get(name, None)
