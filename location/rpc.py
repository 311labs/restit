from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import permission_required
from django.db.models import Q

from rest.decorators import *
from rest.views import *
from rest import UberDict

from datetime import datetime
import random

from .models import *

@urlGET (r'^(?P<zip_code>[0-9]{5}(-[0-9]{4})?)$')
@login_required
def locationsByZipCode(request, zip_code):
    res = GeoLocation.objects.filter(zip=zip_code)
    return restList(request, res)

@urlGET (r'^near/(?P<zip_code>[0-9]{5}(-[0-9]{4})?)$')
@login_required
def locationsByZipCode(request, zip_code):
    res = GeoLocation.nearZip(zip_code, float(request.DATA.get("distance", 10)))
    return restList(request, res)

@urlPOST (r'^track$')
@login_required
def createTrack(request):
    """
    Creates a new track
    requires a user
    """
    kind = request.POST.get("kind", None)
    if kind is None:
        return restStatus(request, False, error="requires a kind of track")

    ref_id = request.POST.get("ref_id", None)
    if ref_id is None:
        return restStatus(request, False, error="requires a valid reference id")

    name = request.POST.get("name", "Generic Track")

    track = GeoTrack(owner=request.user, kind=kind, ref_id=int(ref_id), name=name)
    track.save()

    if "pos_lat" in request.POST:
        lat = request.POST.get("pos_lat")
        lng = request.POST.get("pos_lng")
        if lat != None:
            elevation = request.POST.get("pos_elevation", 0.0)
            accuracy = request.POST.get("pos_accuracy", 0.0)
            altitude = request.POST.get("pos_altitude", 0.0)
            altitudeAccuracy = request.POST.get("pos_altitudeAccuracy", 0.0)
            heading = request.POST.get("pos_heading", 0.0)
            speed = request.POST.get("pos_speed", 0.0)

            pos = GeoPosition(track=track, lat=lat, lng=lng,
                elevation=elevation,
                accuracy=accuracy,
                altitude=altitude,
                altitudeAccuracy=altitudeAccuracy,
                heading=heading,
                speed=speed)
            pos.save()
    return restGet(request, track)

@urlPOST (r'^track/(?P<track_id>\d+)$')
@login_required
def addTrackPos(request, track_id):
    try:
        track = GeoTrack.objects.get(pk=track_id)
    except:
        return restStatus(request, False, error="invalid track")

    if request.user.id != track.owner.id:
        return restStatus(request, False, error="permission denied")


    if "lat" not in request.DATA or "lng" not in request.DATA:
        return restStatus(request, False, error="requires valid position")

    lat = request.POST.get("lat")
    lng = request.POST.get("lng")

    elevation = request.POST.get("elevation", 0.0)
    accuracy = request.POST.get("accuracy", 0.0)
    altitude = request.POST.get("altitude", 0.0)
    altitudeAccuracy = request.POST.get("altitudeAccuracy", 0.0)
    heading = request.POST.get("heading", 0.0)
    speed = request.POST.get("speed", 0.0)

    pos = GeoPosition(track=track, lat=lat, lng=lng,
        elevation=elevation,
        accuracy=accuracy,
        altitude=altitude,
        altitudeAccuracy=altitudeAccuracy,
        heading=heading,
        speed=speed)
    pos.save()
    return restStatus(request, True)

@urlGET (r'^track/(?P<track_id>\d+)$')
@login_required
def getTrackPositions(request, track_id):
    try:
        track = GeoTrack.objects.get(pk=track_id)
    except:
        return restStatus(request, False, error="invalid track")

    ret = GeoPosition.objects.filter(track=track).order_by("created")
    if "last_pos_time" in request.DATA:
        last_pos_time = datetime.fromtimestamp(float(request.DATA.get("last_pos_time", 0)))
        ret = ret.filter(created__gte=last_pos_time)
    return restList(request, ret)

@urlGET (r'^users$')
def getIPLocations(request):
    locs = GeoIPLocation.objects.filter(owner__isnull=False)
    return restList(request, locs, exclude=["owner"])

@urlGET (r'^ip$')
def getPublicIP(request):
    gip = GeoIP.get(request.ip)
    graph = request.DATA.get("graph", "default")
    return gip.restGet(request, graph)

@urlGET (r'^ip/lookup$')
def getPublicIP(request):
    ip = request.DATA.get("ip", request.ip)
    gip = GeoIP.get(
        ip,
        force_refresh=request.DATA.get("refresh", 0, field_type=bool),
        stale_after=request.DATA.get("stale_after", 90, field_type=int))
    graph = request.DATA.get("graph", "default")
    return gip.restGet(request, graph)

@url(r'^timezone$')
def getTimezone(request):
    lat = request.DATA.get(["lat", "latitude"])
    lng = request.DATA.get(["lng", "longitude"])
    zipcode = request.DATA.get(["zipcode", "zip"])

    if lat and lng:
        res = geolocate.GeoTimeZone(lat, lng)
        return restGet(request, res.asDict())
    return restStatus(request, False, error="requires zip or lat/lng")

@url(r'^address$')
def getTimezone(request):
    lat = request.DATA.get(["lat", "latitude"])
    lng = request.DATA.get(["lng", "longitude"])
    zipcode = request.DATA.get(["zipcode", "zip"])

    if lat and lng:
        res = geolocate.reverse(lat, lng)
        if res:
            return restGet(request, res.asDict())
        return "invalid response from host"
    return restStatus(request, False, error="requires zip or lat/lng")

@url(r'^address/generator$')
def on_fake_address(request):
    addr = getFakeAddress()
    return restGet(request, addr)

