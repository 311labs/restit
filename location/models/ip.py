from django.db import models
from rest import models as rm
from rest import settings
from datetime import datetime, timedelta
from .. import geolocate

GEOIP_LOOKUP_BY_SUBNET = settings.get("GEOIP_LOOKUP_BY_SUBNET", True)


class GeoIP(models.Model, rm.RestModel):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    hostname = models.CharField(max_length=255, blank=True, null=True, default=None)
    ip = models.CharField(max_length=64, db_index=True)
    subnet = models.CharField(max_length=64, db_index=True, default=None, null=True)
    isp = models.CharField(max_length=84)

    city = models.CharField(max_length=64, blank=True, null=True)
    state = models.CharField(max_length=64, blank=True, null=True)
    country = models.CharField(max_length=64, blank=True, null=True)
    postal = models.CharField(max_length=32, blank=True, null=True)

    lat = models.FloatField(default=0.0, blank=True)
    lng = models.FloatField(default=0.0, blank=True)

    def __str__(self):
        return f"<GeoIP: {self.ip} {self.lat}:{self.lng}"

    def isStale(self, days=300):
        stale = self.modified + timedelta(days=days)
        return stale < datetime.now()

    def refresh(self, using=None):
        if self.ip == "127.0.0.1":
            self.isp = "local"
            self.hostname = "localhost"
            self.subnet = "127.0.0"
            self.modified = datetime.now()
            self.save(using=using)
            return
        res = geolocate.locateByIP(self.ip)
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
    def get(cls, ip, force_refresh=False, stale_after=300):
        return cls.lookup(ip, force_refresh, stale_after)

    @classmethod
    def lookup(cls, ip, force_refresh=False, stale_after=300, using=None):
        if not geolocate.isIP(ip):
            ip = geolocate.dnsToIP(ip)
        subnet = ip[:ip.rfind(".")]
        gip = GeoIP.objects.filter(ip=ip).first()
        if gip is None:
            gip = GeoIP(ip=ip, subnet=subnet)
            if GEOIP_LOOKUP_BY_SUBNET:
                subgip = GeoIP.objects.filter(subnet=subnet).last()
                if subgip:
                    gip.lat = subgip.lat
                    gip.lng = subgip.lng
                    gip.city = subgip.city
                    gip.state = subgip.state
                    gip.country = subgip.country
                    gip.postal = subgip.postal
                    gip.isp = subgip.isp
                    gip.save()
                else:
                    gip.refresh(using=using)
            else:
                gip.refresh(using=using)
        else:
            if force_refresh or gip.isStale(stale_after):
                gip.refresh(using=using)
            elif gip.subnet is None:
                gip.subnet = subnet
                gip.save()
        return gip
