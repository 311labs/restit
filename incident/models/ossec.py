from django.db import models
from django.conf import settings

from rest import models as rm
from rest import helpers as rh


class ServerOssecAlert(models.Model, rm.RestModel):
    # osec alert settings will be managed through metadata
    class RestMeta:
        DEFAULT_SORT = "-id"
        SEARCH_FIELDS = ["rule_id", "hostname", "action"]
        GRAPHS = {
            "default": {
                "graphs": {
                    "geoip": "default"
                }
            },
            "list": {
                "graphs": {
                    "self": "default"
                }
            },
            "detailed": {
                "graphs": {
                    "self": "default"
                }
            }
        }

    created     = models.DateTimeField(db_index=True, auto_now_add=True, editable=False)
    when        = models.DateTimeField(db_index=True)
    alert_id    = models.CharField(max_length=64, blank=False, null=True, default=None)
    rule_id     = models.CharField(db_index=True, max_length=64, blank=False, null=True, default=None)
    text        = models.TextField(null=True, default=None)
    action      = models.CharField(max_length=32, blank=True, null=True, default=None, db_index=True)
    ext_ip      = models.CharField(max_length=32, blank=True, null=True, default=None)
    src_ip      = models.CharField(max_length=32, blank=True, null=True, default=None)
    hostname    = models.CharField(max_length=128, blank=True, null=True, default=None, db_index=True)
    ip          = models.CharField(max_length=32, blank=True, null=True, default=None)
    username    = models.CharField(max_length=64, blank=False, null=True, default=None)
    username2   = models.CharField(max_length=64, blank=False, null=True, default=None)
    ssh_sig     = models.TextField(blank=False, null=True, default=None)

    level       = models.IntegerField(default=0)
    title       = models.CharField(max_length=200, blank=True, null=True, default=None)
    geoip       = models.ForeignKey("location.GeoIP", blank=True, null=True, default=None, on_delete=models.DO_NOTHING)
    
    def __str__(self):
        return f'{self.hostname}: {self.title}'
