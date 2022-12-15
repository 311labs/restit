from django.db import models
from rest import models as rm
from location import geolocate


class GeoIPLocation(models.Model, rm.RestModel):
    # assocate with a user if possible
    owner = models.ForeignKey("account.User", blank=True, null=True, default=None, related_name="locations", on_delete=models.CASCADE)

    # use this to reference a Model
    obj_id = models.IntegerField(blank=True, default=0)
    obj_kind = models.CharField(max_length=64, blank=True, null=True, default="")

    ip = models.CharField(max_length=32)
    created = models.DateTimeField(auto_now_add=True)
    city = models.CharField(max_length=64, blank=True, null=True)
    region = models.CharField(max_length=64)
    country = models.CharField(max_length=64)
    area_codes = models.CharField(max_length=64)
    timezone = models.CharField(max_length=32)
    kind = models.CharField(max_length=32)

    lat = models.FloatField(default=0.0, blank=True)
    lng = models.FloatField(default=0.0, blank=True)

    @staticmethod
    def cloneForOwner(obj, owner):
        clone = obj
        clone.pk = None
        clone.id = None
        clone.owner = owner
        clone.save()
        return clone

    @staticmethod
    def createByIP(ip, owner=None):
        # first check if we have already seen this ip
        locs = GeoIPLocation.objects.filter(ip=ip)
        if locs.count():
            if locs.filter(owner=owner).count():
                return locs.filter(owner=owner).first()
            # clone the first obj
            return GeoIPLocation.cloneForOwner(locs.first(), owner)

        res = geolocate.locateIP(ip)
        obj = None
        if res:
            obj = GeoIPLocation(owner=owner, ip=ip, lat=res["lat"], lng=res["lng"])
            if "city" in res:
                obj.city = res["city"]
            if "country" in res:
                obj.country = res["country"]
            if "region" in res:
                obj.region = res["region"]
            obj.save()
        return obj
