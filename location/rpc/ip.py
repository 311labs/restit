from rest import decorators as rd
from .. import models as location


@rd.urlGET(r'^ip$')
def on_myip(request):
    gip = location.GeoIP.get(request.ip)
    graph = request.DATA.get("graph", "default")
    return gip.restGet(request, graph)


@rd.urlGET(r'^ip/lookup$')
def on_ip_lookup(request):
    ip = request.DATA.get("ip", request.ip)
    gip = location.GeoIP.get(
        ip,
        force_refresh=request.DATA.get("refresh", 0, field_type=bool),
        stale_after=request.DATA.get("stale_after", 90, field_type=int))
    graph = request.DATA.get("graph", "default")
    return gip.restGet(request, graph)


@rd.url(r'^geo/ip$')
@rd.url(r'^geo/ip/(?P<pk>\d+)$')
@rd.login_required
def rest_on_geoip(request, pk=None):
    return location.GeoIP.on_rest_request(request, pk)
