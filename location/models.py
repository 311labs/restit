from django.db import models
from rest.models import RestModel
from rest import UberDict
from . import geolocate
from datetime import datetime, timedelta
import re
import os
import random

def getFakeAddress():
    addresses = UberDict.fromFile(os.path.join(os.path.dirname(__file__), "valid_test_data.json"))
    return random.choice(addresses.addresses)

# Create your models here.

class GeoLocation(models.Model, RestModel):
    city = models.CharField(max_length=64, blank=True, null=True)
    county = models.CharField(max_length=64)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=32)
    country = models.CharField(max_length=64)
    area_codes = models.CharField(max_length=64)
    timezone = models.CharField(max_length=32)
    kind = models.CharField(max_length=32)

    lat = models.FloatField(default=0.0, blank=True)
    lng = models.FloatField(default=0.0, blank=True)

    @staticmethod
    def isValidZip(zipcode):
        return len(zipcode) > 2

    @staticmethod
    def findByZip(zipcode):
        return GeoLocation.objects.filter(zip=zipcode)

    @classmethod
    def byZip(cls, zipcode):
        cached = cls.objects.filter(zip=zipcode).last()
        if cached: return cached
        model = None
        try:
            loc = geolocate.search(zipcode).asDict()
            timezone = geolocate.getTZ(loc.get("latitude"), loc.get("longitude"))

            model = cls(
                city=loc.get("city"),
                county=loc.get("county", "n/a"),
                state=loc.get("short_administrative_area_level_1", "n/a"),
                zip=zipcode,
                country=loc.get("country"),
                timezone=timezone.get("timeZoneId"),
                lat=loc.get("latitude"),
                lng=loc.get("longitude"),
            )
            if model.county is None:
                model.county = "n/a"
            model.save()
        except Exception as e:
            print(("GeoLocation.byZip({}) ERROR: {}".format(zipcode, str(e))))
        return model


    @staticmethod
    def nearZip(zipcode, distance_miles=10):
        res = GeoLocation.objects.filter(zip=zipcode)
        # take the first one
        # TODO FIX ME
        distance = 0.01 * distance_miles
        if res.count():
            loc = res[0]
            # now adjust lat lng, poor mans approach
            blat = loc.lat + distance
            slat = loc.lat - distance
            blng = loc.lng + distance
            slng = loc.lng - distance
            res = GeoLocation.objects.filter(lat__lte=blat, lat__gte=slat, lng__lte=blng, lng__gte=slng)
        return res

class GeoTrack(models.Model, RestModel):
    uid = models.CharField(max_length=124, db_index=True, null=True, default=None)
    owner = models.ForeignKey("account.User", null=True, default=None, on_delete=models.CASCADE)
    name = models.CharField(max_length=124)
    kind = models.CharField(max_length=64)
    ref_id = models.IntegerField(blank=True, default=0)
    created = models.DateTimeField(auto_now_add=True)

    def getPositions(self):
        return self.positions.all().order_by("created")

    def getCurrentPosition(self):
        positions = self.getPositions()
        if positions.count():
            return positions[0]
        return None

class GeoPosition(models.Model, RestModel):
    uid = models.CharField(max_length=124, db_index=True, null=True, default=None)
    track = models.ForeignKey(GeoTrack, blank=True, null=True, default=None, related_name="positions", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    lat = models.FloatField(default=0.0)
    lng = models.FloatField(default=0.0)
    elevation = models.FloatField(default=0.0, blank=True)
    accuracy = models.FloatField(default=0.0, blank=True)
    altitude = models.FloatField(default=0.0, blank=True)
    altitudeAccuracy = models.FloatField(default=0.0, blank=True)
    heading = models.FloatField(default=0.0, blank=True)
    speed = models.FloatField(default=0.0, blank=True)



class GeoIP(models.Model, RestModel):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    hostname = models.CharField(max_length=255, blank=True, null=True, default=None)
    ip = models.CharField(max_length=64)
    isp = models.CharField(max_length=84)

    city = models.CharField(max_length=64, blank=True, null=True)
    state = models.CharField(max_length=64, blank=True, null=True)
    country = models.CharField(max_length=64, blank=True, null=True)
    postal = models.CharField(max_length=32, blank=True, null=True)

    lat = models.FloatField(default=0.0, blank=True)
    lng = models.FloatField(default=0.0, blank=True)

    def refresh(self, using=None):
        if self.ip == "127.0.0.1":
            self.isp = "local"
            self.hostname = "localhost"
            self.modified = datetime.now()
            self.save(using=using)
            return
        res = geolocate.ip(self.ip)
        if res is None:
            # just save the
            if not self.pk:
                self.isp = "unknown"
            self.modified = datetime.now()
            self.save(using=using)
            return
        self.hostname = res.hostname
        self.isp = res.isp
        if self.isp is None:
            self.isp = "unknown"
        self.city = res.city
        self.state = res.state
        self.country = res.country
        self.postal = res.postal
        try:
            self.lat = float(res.latitude)
            self.lng = float(res.longitude)
        except Exception:
            pass
        self.save(using=using)

    @classmethod
    def get(cls, ip, force_refresh=False, stale_after=90):
        return cls.lookup(ip, force_refresh, stale_after)

    @classmethod
    def lookup(cls, ip, force_refresh=False, stale_after=90, using=None):
        if not geolocate.is_ip(ip):
            ip = geolocate.dns_to_ip(ip)
        if using:
            gip = GeoIP.objects.using(using).filter(ip=ip).first()
        else:
            gip = GeoIP.objects.filter(ip=ip).first()
        if gip is None:
            gip = GeoIP(ip=ip)
            gip.refresh(using=using)
        else:
            stale = datetime.now() - timedelta(days=stale_after)
            if force_refresh or gip.created < stale:
                gip.refresh(using=using)
        return gip

class GeoIPLocation(models.Model, RestModel):
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

        res = geolocate.ip(ip)
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

class Address(models.Model, RestModel):
    class RestMeta:
        GRAPHS = {
            "abstract": {
                "fields":[
                    ('line1', 'street1'),
                    ('line2', 'street2'),
                    'city',
                    'state',
                    ('postalcode', 'zip'),
                    'country',
                ]
            }
        }
    modified_by = models.ForeignKey("account.User", null=True, blank=True, default=None, on_delete=models.CASCADE)
    modified = models.DateTimeField(auto_now=True)
    line1 = models.CharField(max_length=255, blank=True, null=True, default=None)
    line2 = models.CharField(max_length=255, blank=True, null=True, default=None)
    city = models.CharField(max_length=127, blank=True, null=True, default=None)
    state = models.CharField(max_length=127, blank=True, null=True, default=None)
    county = models.CharField(max_length=127, blank=True, null=True, default=None)
    country = models.CharField(max_length=16, blank=True, null=True, default=None)
    postalcode = models.CharField(max_length=32, blank=True, null=True, default=None)
    lat = models.FloatField(default=0.0, blank=True)
    lng = models.FloatField(default=0.0, blank=True)

    def getTimezone(self):
        if self.lat:
            return geolocate.getTZ(self.lat, self.lng)
        return None

    def refresh(self):
        try:
            res = geolocate.search("{}, {}, {}".format(self.line1, self.city, self.state))
            self.county = res.county
            self.country = res.short_country
            self.lat = res.latitude
            self.lng = res.longitude
            super(Address, self).save()
        except:
            pass

    def save(self, *args, **kwargs):
        if not self.lat:
            self.refresh()
        super(Address, self).save(*args, **kwargs)

