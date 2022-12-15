from rest import decorators as rd
from rest import views as rv
from .. import models as location
from datetime import datetime


@rd.urlGET(r'^(?P<zip_code>[0-9]{5}(-[0-9]{4})?)$')
@rd.login_required
def on_location_byzip(request, zip_code):
    res = location.GeoLocation.objects.filter(zip=zip_code)
    return rv.restList(request, res)


@rd.urlGET(r'^near/(?P<zip_code>[0-9]{5}(-[0-9]{4})?)$')
@rd.login_required
def on_location_nearzip(request, zip_code):
    res = location.GeoLocation.nearZip(zip_code, float(request.DATA.get("distance", 10)))
    return rv.restList(request, res)


@rd.url(r'^geo/location$')
@rd.url(r'^geo/location/(?P<pk>\d+)$')
@rd.login_required
def rest_on_geolocation(request, pk=None):
    return location.GeoLocation.on_rest_request(request, pk)
