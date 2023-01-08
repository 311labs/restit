from rest import settings
from django.template.defaultfilters import slugify as django_slugify
from collections import OrderedDict
from datetime import datetime, timedelta

app_settings = settings.getAppSettings("metrics")
GRANULARITIES = ['seconds', 'minutes', 'hourly', 'daily', 'weekly', 'monthly', 'yearly']


def to_string(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value


def to_int_list(values):
    """Converts the given list of vlues into a list of integers. If the
    integer conversion fails (e.g. non-numeric strings or None-values), this
    filter will include a 0 instead."""
    results = []
    for v in values:
        try:
            results.append(int(v))
        except (TypeError, ValueError):
            results.append(0)
    return results


def to_int(value):
    """Converts the given string value into an integer. Returns 0 if the
    conversion fails."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def strip_metric_prefix(value):
    """Strips the "m:<slug>" prefix from a metric.
    Applying this filter to the keys for each metric will have the following
    results:

    * Seconds -- from: ``m:<slug>:s:<yyyy-mm-dd-hh-MM-SS>`` to ``<yyyy-mm-dd-hh-MM-SS>``
    * Minutes -- from: ``m:<slug>:i:<yyyy-mm-dd-hh-MM>`` to ``<yyyy-mm-dd-hh-MM>``
    * Hourly -- from: ``m:<slug>:h:<yyyy-mm-dd-hh>`` to ``<yyyy-mm-dd-hh>``
    * Daily -- from: ``m:<slug>:<yyyy-mm-dd>`` to ``<yyyy-mm-dd>``
    * Weekly -- from ``m:<slug>:w:<num>`` to ``w:<num>``
    * Monthly -- from ``m:<slug>:m:<yyyy-mm>`` to ``m:<yyyy-mm>``
    * Yearly -- from ``m:<slug>:y:<yyyy>`` to ``y:<yyyy>``

    """
    return ':'.join(value.split(":")[2:])


def metric_slug(value):
    """Given a redis key value for a metric, returns only the slug.
    Applying this filter to the keys for each metric will have the following
    results:

    * Converts ``m:foo:s:<yyyy-mm-dd-hh-MM-SS>`` to ``foo``
    * Converts ``m:foo:i:<yyyy-mm-dd-hh-MM>`` to ``foo``
    * Converts ``m:foo:h:<yyyy-mm-dd-hh>`` to ``foo``
    * Converts ``m:foo:<yyyy-mm-dd>`` to ``foo``
    * Converts ``m:foo:w:<num>`` to ``foo``
    * Converts ``m:foo:m:<yyyy-mm>`` to ``foo``
    * Converts ``m:foo:y:<yyyy>`` to ``foo``

    """
    return value.split(":")[1]


def granularities(min_granularity=None):
    """Returns a generator of all possible granularities based on the
    MIN_GRANULARITY and MAX_GRANULARITY settings.
    """
    if min_granularity is None:
        min_granularity = app_settings.MIN_GRANULARITY
    keep = False
    for g in GRANULARITIES:
        if g == min_granularity and not keep:
            keep = True
        elif g == app_settings.MAX_GRANULARITY and keep:
            keep = False
            yield g
        if keep:
            yield g


def get_metric_key_pattern(granularity, slug, date):
    """ The Redis metric key and date formatting patterns for each key, by granularity"""
    patterns_by_granularity = {
        "seconds": {"key": "m:{0}:s:{1}", "date_format": "%Y-%m-%d-%H-%M-%S"},
        "minutes": {"key": "m:{0}:i:{1}", "date_format": "%Y-%m-%d-%H-%M"},
        "hourly": {"key": "m:{0}:h:{1}", "date_format": "%Y-%m-%d-%H"},
        "daily": {"key": "m:{0}:{1}", "date_format": "%Y-%m-%d"},
        "weekly": {
            "key": "m:{0}:w:{1}",
            "date_format": get_weekly_date_format(date),
        },
        "monthly": {"key": "m:{0}:m:{1}", "date_format": "%Y-%m"},
        "yearly": {"key": "m:{0}:y:{1}", "date_format": "%Y"},
    }
    pattern_for_granularity = patterns_by_granularity[granularity]
    fmt = pattern_for_granularity["date_format"]
    date_string = date.strftime(fmt)
    return pattern_for_granularity["key"].format(slug, date_string)


def get_weekly_date_format(date):
    if app_settings.USE_ISO_WEEK_NUMBER:
        # We can return instantly because ISO week start on monday
        return "{year}-{week_no}".format(year=date.isocalendar()[0], week_no=date.isocalendar()[1])
    return "%Y-%{0}".format('W' if app_settings.MONDAY_FIRST_DAY_OF_WEEK else 'U')


def get_weekly_date(date):
    return date.replace(hour=0, minute=0, second=0) - timedelta(days=date.weekday())


def build_key_patterns(slug, date, min_granularity=None):
    """Builds an OrderedDict of metric keys and patterns for the given slug
    and date."""
    # we want to keep the order, from smallest to largest granularity
    patts = OrderedDict()
    for g in granularities(min_granularity=min_granularity):
        patts[g] = get_metric_key_pattern(g, slug, date)
    return patts


def slugify(slug):
    return slug.replace(" ", "_").replace(":", "|").lower()


def build_keys(slug, date=None, granularity='all', min_granularity=None):
    """Builds redis keys used to store metrics.

    * ``slug`` -- a slug used for a metric, e.g. "user-signups"
    * ``date`` -- (optional) A ``datetime.datetime`` object used to
      generate the time period for the metric. If omitted, the current date
      and time (in UTC) will be used.
    * ``granularity`` -- Must be one of: "all" (default), "yearly",
    "monthly", "weekly", "daily", "hourly", "minutes", or "seconds".

    Returns a list of strings.

    """
    slug = slugify(slug)  # Ensure slugs have a consistent format
    if date is None:
        date = datetime.utcnow()
    if min_granularity is None and granularity != "all":
        min_granularity = granularity
    patts = build_key_patterns(slug, date, min_granularity=min_granularity)
    if granularity == "all":
        return list(patts.values())
    return [patts[granularity]]


def date_for_granulatiry(date, granularity):
    if granularity == "minutes":
        return date.replace(second=0, microsecond=0)
    elif granularity == "hourly":
        return date.replace(minute=0, second=0, microsecond=0)
    elif granularity == "daily":
        return date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif granularity == "weekly":
        return get_weekly_date(date)
    elif granularity == "monthly":
        return date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def date_range(granularity, since, to=None):
    """Returns a generator that yields ``datetime.datetime`` objects from
    the ``since`` date until ``to`` (default: *now*).

    * ``granularity`` -- The granularity at which the generated datetime
      objects should be created: seconds, minutes, hourly, daily, weekly,
      monthly, or yearly
    * ``since`` -- a ``datetime.datetime`` object, from which we start
      generating periods of time. This can also be ``None``, and will
      default to the past 7 days if that's the case.
    * ``to`` -- a ``datetime.datetime`` object, from which we start
      generating periods of time. This can also be ``None``, and will
      default to now if that's the case.

    If ``granularity`` is one of daily, weekly, monthly, or yearly, this
    function gives objects at the daily level.

    If ``granularity`` is one of the following, the number of datetime
    objects returned is capped, otherwise this code is really slow and
    probably generates more data than we want:

        * hourly: returns at most 720 values (~30 days)
        * minutes: returns at most 480 values (8 hours)
        * second: returns at most 300 values (5 minutes)

    For example, if granularity is "seconds", we'll receive datetime
    objects that differ by 1 second each.

    """
    if since is None:
        since = datetime.utcnow() - timedelta(days=7)  # Default to 7 days

    if to is None:
        to = datetime.utcnow()
    elapsed = (to - since)

    # Figure out how many units to generate for the elapsed time.
    # I'm going to use `granularity` as a keyword parameter to timedelta,
    # so I need to change the wording for hours and anything > days.
    if granularity == "seconds":
        units = elapsed.total_seconds()
        units = 300 if units > 300 else units
    elif granularity == "minutes":
        units = elapsed.total_seconds() / 60
        units = 480 if units > 480 else units
    elif granularity == "hourly":
        granularity = "hours"
        units = elapsed.total_seconds() / 3600
        units = 720 if units > 720 else units
    elif granularity == "daily":
        granularity = "days"
        units = elapsed.days + 1
    elif granularity == "monthly":
        granularity = "days"
        months = diff_month(to, since)
        output = []
        for i in range(months):
            output.append(to.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
            to -= timedelta(days=31)
        return output

    return (to - timedelta(**{granularity: u}) for u in range(int(units)))


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month
