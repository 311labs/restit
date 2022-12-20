from django.db import models
from django.db.models import Sum, Max, Count, Q
from django.db.models.functions import Trunc
from rest import helpers as rh
from rest import models as rm
from objict import objict
from . import utils


def metric(slug, keys, data, min_granularity="hourly", group=None, date=None):
    # keys is a ordered list of keys to map to k1,k2,etc
    # data is a dict of key/values
    uuid_key = generate_uuid(slug, group)
    granularities = utils.granularities(min_granularity)
    date = date
    if date is None:
        date = utils.datetime.utcnow()
    uuids = utils.build_keys(uuid_key, date, min_granularity=min_granularity)
    for granularity, key in zip(granularities, uuids):
        m, created = Metrics.objects.get_or_create(
            uuid=key, 
            defaults=dict(
                granularity=granularity, slug=slug,
                group=group, start=utils.date_for_granulatiry(date, granularity)))
        m.updateMetrics(keys, data, created)


def get_totals(slug, keys, granularity, start, end=None, group=None):
    start = utils.date_for_granulatiry(start, granularity)
    if end is None:
        end = utils.datetime.utcnow()
    end = utils.date_for_granulatiry(end, granularity)
    qset = Metrics.objects.filter(
        slug=slug, granularity=granularity,
        group=group, start__gte=start, start__lte=end)
    vkeys = [f"v{i}" for i in range(1, len(keys)+1)]
    sums = rh.getSum(qset, *vkeys)
    out = objict()
    i = 1
    for k in keys:
        out[k] = sums[f"v{i}"]
        i += 1
    return objict(slug=slug, granularity=granularity, start=start, end=end, values=out)


def get_metrics(slug, keys, granularity, start, end=None, group=None):
    """
    returns data ready for Chart.js
    'periods': ['y:2012', 'y:2013', 'y:2014']
    'data': [
      {
        'slug': 'bar',
        'values': [1, 2, 3]
      },
      {
        'slug': 'foo',
        'values': [4, 5, 6]
      },
    ]
    """
    start = utils.date_for_granulatiry(start, granularity)
    if end is None:
        end = utils.datetime.utcnow()
    end = utils.date_for_granulatiry(end, granularity)
    qset = Metrics.objects.filter(
        slug=slug, granularity=granularity,
        group=group, start__gte=start, start__lte=end)
    raw_metrics = dict()
    for obj in qset:
        raw_metrics[utils.strip_metric_prefix(obj.uuid)] = obj.getMetrics()
    periods = []
    data = dict()
    for k in keys:
        data[k] = []
    for date in utils.date_range(granularity, start, end):
        period = utils.strip_metric_prefix(utils.build_keys(slug, date, granularity)[0])
        periods.append(period)
    periods.reverse()
    for period in periods:
        if period not in raw_metrics:
            for k in keys:
                data[k].append(0)
        else:
            values = raw_metrics[period]
            for k in keys:
                data[k].append(values.get(k, 0))
    return objict(periods=periods, data=data)


def generate_uuid(slug, group):
    if group is not None:
        return f"{slug}__{group.pk}"
    return slug


class Metrics(models.Model, rm.RestModel):
    class RestMeta:
        GRAPHS = {
            "default": {
                "recurse_into": ["generic__component"]
            }
        }

    created = models.DateTimeField(auto_now_add=True, editable=True)
    # timeframe of metrics
    start = models.DateTimeField(db_index=True)
    granularity = models.CharField(max_length=64, db_index=True)
    # unique uuid of metric
    uuid = models.SlugField(max_length=124, unique=True)
    # kind/slug of metric
    slug = models.SlugField(max_length=124, db_index=True)
    # allow to group metrics by a group
    group = models.ForeignKey("account.Group", related_name="+", on_delete=models.CASCADE, null=True, default=None)

    # now we create a set of k/v 
    k1 = models.SlugField(max_length=64, null=True, default=None)
    v1 = models.IntegerField(default=0)

    k2 = models.SlugField(max_length=64, null=True, default=None)
    v2 = models.IntegerField(default=0)

    k3 = models.SlugField(max_length=64, null=True, default=None)
    v3 = models.IntegerField(default=0)

    k4 = models.SlugField(max_length=64, null=True, default=None)
    v4 = models.IntegerField(default=0)

    k5 = models.SlugField(max_length=64, null=True, default=None)
    v5 = models.IntegerField(default=0)

    k6 = models.SlugField(max_length=64, null=True, default=None)
    v6 = models.IntegerField(default=0)

    k7 = models.SlugField(max_length=64, null=True, default=None)
    v7 = models.IntegerField(default=0)

    k8 = models.SlugField(max_length=64, null=True, default=None)
    v8 = models.IntegerField(default=0)

    k9 = models.SlugField(max_length=64, null=True, default=None)
    v9 = models.IntegerField(default=0)

    k10 = models.SlugField(max_length=64, null=True, default=None)
    v10 = models.IntegerField(default=0)

    k11 = models.SlugField(max_length=64, null=True, default=None)
    v11 = models.IntegerField(default=0)

    k12 = models.SlugField(max_length=64, null=True, default=None)
    v12 = models.IntegerField(default=0)

    k13 = models.SlugField(max_length=64, null=True, default=None)
    v13 = models.IntegerField(default=0)

    k14 = models.SlugField(max_length=64, null=True, default=None)
    v14 = models.IntegerField(default=0)

    def getMetrics(self):
        metrics = objict()
        for i in range(1, 15):
            key = getattr(self, f"k{i}", None)
            if key is None:
                return metrics
            metrics[key] = getattr(self, f"v{i}", 0)
        return metrics

    def updateMetrics(self, keys, data, update_keys=False):
        params = {}
        index = 0
        for key in keys:
            if isinstance(data, list):
                v = data[index]
            else:
                v = data[key]
            index += 1
            vkey = f"v{index}"
            params[vkey] = models.F(vkey) + v
            if update_keys:
                params[f"k{index}"] = key
        Metrics.objects.filter(pk=self.pk).update(**params)

