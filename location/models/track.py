from django.db import models
from rest import models as rm


class GeoTrack(models.Model, rm.RestModel):
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


class GeoPosition(models.Model, rm.RestModel):
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
