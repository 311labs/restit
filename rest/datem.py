
from dateutil.parser import parse as date_parser
from datetime import date, datetime, timedelta
import calendar
import pytz
import time
import re


def convertToEpoch(dt):
    return time.mktime(dt.timetuple())

def getShortTZ(zone, when=None):
    timezone = pytz.timezone(zone)
    if not when:
        when = datetime.today()
    ltz = timezone.localize(when, is_dst=None)
    return ltz.tzname()

def convertToLocalTime(zone, when=None):
    """
    convert timezones in python can result in minutes shifting...
    just do a simple hour offset with timedelta
    """
    if when is None:
        when = datetime.today()

    offset = getTimeZoneOffset(zone, when)
    if offset >= 0:
        when = when - timedelta(hours=offset)
    else:
        when = when + timedelta(hours=offset)
    return when

def convertToUTC(zone, when=None):
    # this works because it gets around the issue with naive vs aware
    offset = getTimeZoneOffset(zone, when)
    if offset >= 0:
        when = when + timedelta(hours=offset)
    else:
        when = when - timedelta(hours=offset)
    return when

def convertToUTCEx(zone, when):
    local = pytz.timezone(zone)
    local_dt = local.localize(when, is_dst=None)
    return local_dt.astimezone(pytz.utc)

def getUTC(zone, when=None):
    timezone = pytz.timezone(zone)
    if when is None:
        when = datetime.today()
    return timezone.utcoffset(when)

def getTimeZoneOffset(zone, when=None, hour=None, dst=True):
    if zone is None:
        zone = "UTC"
    timezone = pytz.timezone(zone)
    if not when:
        when = datetime.today()
    timestamp = when
    if hour != None:
        when = when.replace(tzinfo=pytz.UTC, hour=hour)
    else:
        hour = 0
        when = when.replace(tzinfo=pytz.UTC)

    offset = int(when.astimezone(timezone).utcoffset().total_seconds()/3600)
    if not dst:
        offset = when.astimezone(timezone).utcoffset() - timezone.dst(timestamp)
        offset = int(offset.total_seconds()/3600)
    # if hour != None:
    offset = abs(offset) + hour
    if offset >= 24:
        offset -= 24
    return offset

def diffNow(dt):
    return diffSeconds(datetime.now(), dt)

def diffSeconds(t1, t2):
    return (t1 - t2).total_seconds()

def diffMinutes(t1, t2):
    diff = t1 - t2
    days, seconds = diff.days, diff.seconds
    hours = (days * 24)
    return (seconds / 60) + (hours * 60)

def diffHours(t1, t2):
    return diffMinutes(t1, t2) / 60


def next_weekday(d, weekday):
    return d + timedelta(days=((weekday - d.weekday()) + 7) % 7)

def prev_weekday(d, weekday):
    return d - timedelta(days=((d.weekday() - weekday) + 7) % 7)

def getWeek(start, start_day=0):
    # TODO allow selection of start day of week, where Monday is 0 and Sunday is 6
    # get records between last Monday and next Sunday
    week_start = start + timedelta(days=-start.weekday())
    week_end = start + timedelta(days=-start.weekday() - 1, weeks=1)
    return week_start, week_end

def getEndOfMonth(start):
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=calendar.monthrange(start.year, start.month)[1])
    end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    return end


def parseDate(date_str, is_future=False, is_past=False, month_end=True, as_date=False):
    res = parseDateTime(date_str, is_future, is_past, month_end)
    if as_date and res:
        return date(res.year, res.month, res.day)
    return res

def parseDateTime(date_str, is_future=False, is_past=False, month_end=True):
        if type(date_str) in [str, str]:
            dt = None
            if len(date_str) > 6 and date_str.count('.') <= 1 and date_str.split('.')[0].isdigit():
                try:
                    f = float(date_str)
                    return datetime.utcfromtimestamp(f)
                except Exception as err:
                    print(err)
            else:
                fix_month = False
                if date_str.count('-') or date_str.count('/') or date_str.count(' ') or date_str.count('.'):
                    dts = re.split('/|-| |\.',date_str)
                    if len(dts) == 2:
                        date_str = "{0}-01-{1}".format(dts[0], dts[1])
                    else:
                        "-".join(dts)
                elif len(date_str) == 4:
                    fix_month = month_end
                    date_str = date_str[:2] + "-01-" + date_str[2:4]
                elif len(date_str) == 3:
                    date_str = date_str[0] + "/1/" + date_str[-2:]
                elif len(date_str) == 6:
                    date_str = date_str[:2] + "-" + date_str[2:4] +  "-" + date_str[4:6]
            try:
                # print "parse date: {}".format(date_str)
                dt = date_parser(date_str)
                if is_future and dt.year < 2000:
                    dt = dt.replace(year=dt.year+100)
                elif is_past and dt.year >= 2000:
                    dt = dt.replace(year=dt.year-100)
                # print dt
                if fix_month:
                    dt = dt.replace(day=calendar.monthrange(dt.year, dt.month)[1])
                # print dt
                return dt
            except BaseException:
                pass

        elif type(date_str) in [date, datetime]:
            return date_str
        elif type(date_str) in [float, int]:
            return datetime.utcfromtimestamp(date_str)
        return None


def getDateRangeZ(start, end=None, kind=None, zone=None, hour=0, eod=None, end_eod=None):
    return getDateRange(start, end, kind, zone, hour, eod, end_eod)


def getDateRange(start, end=None, kind=None, zone=None, hour=0, eod=None, end_eod=None):
    if start is None:
        start = datetime.today()
    if eod is None:
        eod = 0
    if zone:
        start = convertToLocalTime(zone, parseDate(start))
    if end:
        end = convertToLocalTime(zone, parseDate(end))
        if end == start:
            end = None

    if kind:
        start = start.replace(minute=0, second=0, microsecond=0)
        if kind == "hour":
            end = start + timedelta(hours=1)
        elif kind == "day":
            start = start.replace(hour=eod)
            end = start + timedelta(hours=24)
        elif kind == "week":
            start = start.replace(hour=eod)
            start, end = getWeek(start)
        elif kind == "month":
            start = start.replace(hour=eod, day=1)
            end = getEndOfMonth(start)
        elif kind == "year":
            start = start.replace(hour=eod, day=1, month=1)
            end = getEndOfMonth(start.replace(month=12))
        elif type(kind) is int or (isinstance(kind, str) and kind.isdigit()):
            end = start + timedelta(hours=24)
            start = end - timedelta(days=int(kind))

    if zone or hour:
        if zone is None:
            zone = "UTC"
        offset = getTimeZoneOffset(zone, start, hour=hour)
        if offset:
            start = start + timedelta(hours=offset)
        if end_eod:
            hour = end_eod
        offset = getTimeZoneOffset(zone, end, hour=hour)
        if offset:
            end = end + timedelta(hours=offset)

    return start, end


def getDateRangeEx(start, end=None, kind=None, zone=None, hour=0, eod=None, end_eod=None):
    """
    this function is critical to lookups and the catch here is daylight savings
    the correct approach i believe is to first use UTC to set time frame
    then adjust for timezone offset

    we assume incoming start, end dates are in UTC
    """
    if start is None:
        start = datetime.now()
    if zone is None or zone == "":
        zone = "UTC"
    if start == end:
        end = None
    if eod != None:
        hour = eod

    start = parseDate(start)
    orig_start = start
    if end:
        end = parseDate(end)
        if start == end:
            end = None

    if kind:
        start = start.replace(minute=0, second=0, microsecond=0)
        if kind == "hour":
            end = start + timedelta(hours=1)
        elif kind == "day":
            start = start.replace(hour=0)
            end = start + timedelta(hours=24)
        elif kind == "week":
            start = start.replace(hour=0)
            start, end = getWeek(start)
        elif kind == "month":
            start = start.replace(hour=0, day=1)
            end = getEndOfMonth(start)
        elif kind == "year":
            start = start.replace(hour=0, day=1, month=1)
            end = getEndOfMonth(start.replace(month=12))
        elif type(kind) is int or (isinstance(kind, str) and kind.isdigit()):
            end = start + timedelta(hours=24)
            start = end - timedelta(days=int(kind))
    if end is None:
        end = start + timedelta(hours=24)

    if zone and zone.lower() == "utc":
        zone = None
        if not kind and eod:
            hour = None
    # now lets convert our times to the zone
    if zone or hour:
        if zone is None:
            zone = "UTC"
        offset = getTimeZoneOffset(zone, start, hour=hour)
        if offset:
            start = start + timedelta(hours=offset)
        if end_eod:
            hour = end_eod
        offset = getTimeZoneOffset(zone, end, hour=hour)
        if offset:
            end = end + timedelta(hours=offset)

    # print("daterange: {} to {}".format(start, end))
    return start, end
