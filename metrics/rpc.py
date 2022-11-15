from rest import decorators as rd
from rest import views as rv
from rest import settings
from location.models import GeoIP
from . import client as metrics

"""
Capture simple analytics counters.
"""
LOCATION_METRICS = settings.LOCATION_METRICS


@rd.urlPOST(r'^metric$')
def rest_on_new_metric(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    if data.value is None:
        data.value = 1
    metrics.metric(data.slug, data.value, category=data.catagory, expire=data.expire)
    if LOCATION_METRICS:
        if request.location is None:
            request.location = GeoIP.get(request.ip)
        if request.location and request.location.country:
            country = request.location.country.lower().replace(" ", "_")
            metrics.metric(f"country__{country}__{data.slug}")
    return rv.restStatus(request, True)


@rd.urlGET(r'^metric$')
def rest_on_get_metric(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    result = metrics.get_metric(data.slug)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET(r'^metrics$')
def rest_on_get_metrics(request, pk=None):
    # slug, since, granularity
    slugs = request.DATA.getlist(["slugs", "slug"])
    if slugs is None:
        return rv.restStatus(request, False)
    since = request.DATA.get("since", field_type="datetime")
    granularity = request.DATA.get(["granularity", "period"], default="daily")
    result = metrics.get_metrics(slugs, since, granularity)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET(r'^slugs$')
def rest_on_get_metrics_slugs(request, pk=None):
    slugs = metrics.get_slugs()
    prefix = request.DATA.get("prefix")
    if prefix:
        slugs = [s for s in slugs if s.startswith(prefix)]
    return rv.restReturn(request, dict(data=slugs))


@rd.urlPOST(r'^guage$')
def rest_on_guage(request, pk=None):
    data = request.DATA.toObject()
    if data.slug is None or data.value is None:
        return rv.restStatus(request, False)
    metrics.guage(data.slug, data.value)
    return rv.restStatus(request, True)


@rd.urlGET(r'^guage$')
def rest_on_get_guage(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, metrics.get_guage(data.slug))


@rd.urlGET(r'^guages$')
def rest_on_get_guages(request, pk=None):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slugs is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, metrics.get_guages(data.slugs))


