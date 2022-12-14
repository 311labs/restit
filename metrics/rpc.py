from datetime import datetime
from rest import decorators as rd
from rest import views as rv
from rest import settings
from location.models import GeoIP
from . import client as metrics
from . import models as mm

"""
Capture simple analytics counters.
"""
LOCATION_METRICS = settings.LOCATION_METRICS


@rd.urlPOST('metric')
def rest_on_new_metric(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    if data.value is None:
        data.value = 1
    metrics.metric(data.slug, data.value, category=data.category, expire=data.expire)
    if request.DATA.get("geolocate", False, field_type=bool):
        if request.location is None:
            request.location = GeoIP.get(request.ip)
        if request.location and request.location.country:
            country = request.location.country.lower().replace(" ", "_")
            state = request.location.state.lower().replace(" ", "_")
            metrics.metric(f"geo_country__{country}__{data.slug}", category="geo_country")
            metrics.metric(f"geo_state__{state}__{data.slug}", category="geo_state")
            
    return rv.restStatus(request, True)


@rd.urlGET('metric')
def rest_on_get_metric(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    result = metrics.get_metric(data.slug)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET('metrics')
def rest_on_get_metrics(request, pk=None):
    # slug, since, granularity
    since = request.DATA.get("since", field_type=datetime)
    granularity = request.DATA.get(["granularity", "period"], default="daily")
    category = request.DATA.get("category")
    if category:
        result = metrics.get_category_metrics(category, since, granularity)
        return rv.restReturn(request, dict(data=result))
    slugs = request.DATA.getlist(["slugs", "slug"])
    if slugs is None:
        return rv.restStatus(request, False)

    result = metrics.get_metrics(slugs, since, granularity)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET('slugs')
def rest_on_get_metrics_slugs(request, pk=None):
    category = request.DATA.get("category", None)
    slugs = metrics.get_slugs(category)
    prefix = request.DATA.get("prefix")
    if prefix:
        slugs = [s for s in slugs if s.startswith(prefix)]
    return rv.restReturn(request, dict(data=slugs))


@rd.urlPOST('guage')
def rest_on_guage(request, pk=None):
    data = request.DATA.toObject()
    if data.slug is None or data.value is None:
        return rv.restStatus(request, False)
    metrics.guage(data.slug, data.value)
    return rv.restStatus(request, True)


@rd.urlGET('guage')
def rest_on_get_guage(request):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slug is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, metrics.get_guage(data.slug))


@rd.urlGET('guages')
def rest_on_get_guages(request, pk=None):
    # slug, num=1, category=None, expire=None, date=None
    data = request.DATA.toObject()
    if data.slugs is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, metrics.get_guages(data.slugs))


@rd.urlGET('db/metrics')
def rest_on_get_model_metrics(request, pk=None):
    # slug, since, granularity
    since = request.DATA.get("since", field_type=datetime)
    granularity = request.DATA.get(["granularity", "period"], default="daily")
    category = request.DATA.get("category")
    if category:
        result = mm.get_category_metrics(category, since, granularity)
        return rv.restReturn(request, dict(data=result))
    slugs = request.DATA.get(["slug", "slugs"])
    if slugs is None:
        return rv.restStatus(request, False)

    result = mm.get_metrics(slugs, granularity, since, group=request.group)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET('db/metric')
def rest_on_get_model_metric(request, pk=None):
    # slug, since, granularity
    since = request.DATA.get("since", field_type=datetime)
    granularity = request.DATA.get(["granularity", "period"], default="daily")
    slugs = request.DATA.get(["slug", "slugs"])
    if slugs is None:
        return rv.restStatus(request, False)

    result = mm.get_metric(slugs, granularity, since, group=request.group)
    if result is None:
        return rv.restStatus(request, False)
    return rv.restReturn(request, dict(data=result))


@rd.urlGET('db/slugs')
def rest_on_get_model_metrics_slugs(request, pk=None):
    return rv.restGet(request, dict(data=list(mm.Metrics.objects.all().distinct().values_list("slug", flat=True))))

