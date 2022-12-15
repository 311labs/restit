from django.db import models
from rest import models as rm
from rest import helpers as rh
from .. import geolocate


class Address(models.Model, rm.RestModel):
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
            return geolocate.getTimeZone(self.lat, self.lng)
        return None

    def refresh(self):
        try:
            res = geolocate.search("{}, {}, {}".format(self.line1, self.city, self.state))
            self.county = res.county
            self.country = res.short_country
            self.lat = res.latitude
            self.lng = res.longitude
            super(Address, self).save()
        except Exception:
            rh.log_exception("address.refresh")

    def save(self, *args, **kwargs):
        if not self.lat:
            self.refresh()
        super(Address, self).save(*args, **kwargs)
