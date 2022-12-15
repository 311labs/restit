from rest import decorators as rd
from rest import views as rv
from .. import models as location
from datetime import datetime


@rd.urlPOST(r'^track$')
@rd.login_required
def on_new_track(request):
    """
    Creates a new track
    requires a user
    """
    kind = request.POST.get("kind", None)
    if kind is None:
        return rv.restStatus(request, False, error="requires a kind of track")

    ref_id = request.POST.get("ref_id", None)
    if ref_id is None:
        return rv.restStatus(request, False, error="requires a valid reference id")

    name = request.POST.get("name", "Generic Track")

    track = location.GeoTrack(owner=request.user, kind=kind, ref_id=int(ref_id), name=name)
    track.save()

    if "pos_lat" in request.POST:
        lat = request.POST.get("pos_lat")
        lng = request.POST.get("pos_lng")
        if lat is not None:
            elevation = request.POST.get("pos_elevation", 0.0)
            accuracy = request.POST.get("pos_accuracy", 0.0)
            altitude = request.POST.get("pos_altitude", 0.0)
            altitudeAccuracy = request.POST.get("pos_altitudeAccuracy", 0.0)
            heading = request.POST.get("pos_heading", 0.0)
            speed = request.POST.get("pos_speed", 0.0)

            pos = location.GeoPosition(
                track=track, lat=lat, lng=lng,
                elevation=elevation,
                accuracy=accuracy,
                altitude=altitude,
                altitudeAccuracy=altitudeAccuracy,
                heading=heading,
                speed=speed)
            pos.save()
    return rv.restGet(request, track)


@rd.urlPOST(r'^track/(?P<track_id>\d+)$')
@rd.login_required
def addTrackPos(request, track_id):
    try:
        track = location.GeoTrack.objects.get(pk=track_id)
    except Exception:
        return rv.restStatus(request, False, error="invalid track")

    if request.user.id != track.owner.id:
        return rv.restStatus(request, False, error="permission denied")

    if "lat" not in request.DATA or "lng" not in request.DATA:
        return rv.restStatus(request, False, error="requires valid position")

    lat = request.POST.get("lat")
    lng = request.POST.get("lng")

    elevation = request.POST.get("elevation", 0.0)
    accuracy = request.POST.get("accuracy", 0.0)
    altitude = request.POST.get("altitude", 0.0)
    altitudeAccuracy = request.POST.get("altitudeAccuracy", 0.0)
    heading = request.POST.get("heading", 0.0)
    speed = request.POST.get("speed", 0.0)

    pos = location.GeoPosition(
        track=track, lat=lat, lng=lng,
        elevation=elevation,
        accuracy=accuracy,
        altitude=altitude,
        altitudeAccuracy=altitudeAccuracy,
        heading=heading,
        speed=speed)
    pos.save()
    return rv.restStatus(request, True)


@rd.urlGET(r'^track/(?P<track_id>\d+)$')
@rd.login_required
def getTrackPositions(request, track_id):
    try:
        track = location.GeoTrack.objects.get(pk=track_id)
    except Exception:
        return rv.restStatus(request, False, error="invalid track")

    ret = location.GeoPosition.objects.filter(track=track).order_by("created")
    if "last_pos_time" in request.DATA:
        last_pos_time = datetime.fromtimestamp(float(request.DATA.get("last_pos_time", 0)))
        ret = ret.filter(created__gte=last_pos_time)
    return rv.restList(request, ret)


@rd.url(r'^geo/track$')
@rd.url(r'^geo/track/(?P<pk>\d+)$')
@rd.login_required
def rest_on_geolocation(request, pk=None):
    return location.GeoTrack.on_rest_request(request, pk)


@rd.url(r'^geo/position$')
@rd.url(r'^geo/position/(?P<pk>\d+)$')
@rd.login_required
def rest_on_geoposition(request, pk=None):
    return location.GeoPosition.on_rest_request(request, pk)
