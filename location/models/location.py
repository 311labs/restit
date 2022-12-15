from django.db import models
from rest import models as rm
from rest import helpers as rh
from location import geolocate


class GeoLocation(models.Model, rm.RestModel):
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
        model = cls.objects.filter(zip=zipcode).last()
        if model:
            return model
        try:
            loc = geolocate.search(zipcode).asDict()
            timezone = geolocate.getTimeZone(loc.get("latitude"), loc.get("longitude"))

            model = cls(
                city=loc.get("city"),
                county=loc.get("county", "n/a"),
                state=loc.get("short_administrative_area_level_1", "n/a"),
                zip=zipcode,
                country=loc.get("country"),
                timezone=timezone,
                lat=loc.get("latitude"),
                lng=loc.get("longitude"),
            )
            if model.county is None:
                model.county = "n/a"
            model.save()
        except Exception:
            rh.log_exception(f"byZip({zipcode})")
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
