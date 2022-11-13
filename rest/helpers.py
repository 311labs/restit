import sys
import re
import time
from datetime import date, datetime, timedelta
from django.conf import settings
import importlib
from django.db.models import Count, Q, Avg, Sum, Max, Min
from django.db.models.query import QuerySet
from io import StringIO
import base64
import binascii

from .uberdict import UberDict
from .datem import *
from .log import getLogger
import getpass

try:
    from fuzzywuzzy import fuzz
except:
    fuzz = None

# THIS NEEDS A NEW HOME
import shutil
import tempfile
import os
import random, string
import subprocess

ERROR_LOGGER = getLogger("errors", filename="error.log")
AUDIT_LOGGER = getLogger("auditlog", filename="auditlog.log")
AUDITLOG_LOGGER_BY_USER = getattr(settings, "AUDITLOG_LOGGER_BY_USER", False)
AUDITLOG_LOGGER_BY_TERMINAL = getattr(settings, "AUDITLOG_LOGGER_BY_TERMINAL", False)
AUDITLOG_LOGGERS = getattr(settings, "AUDITLOG_LOGGERS", {})
HELPER_CACHE = UberDict()

def getLoggerByRequest(request):
    logger = AUDIT_LOGGER

    if AUDITLOG_LOGGER_BY_USER and request and request.user.is_authenticated:
        return getLogger(request.user.username, "{}.log".format(request.user.username))
    elif AUDITLOG_LOGGERS:
        for path, key in list(AUDITLOG_LOGGERS.items()):
            # print(("{}: {}".format(path, key)))
            if request.path.startswith(path):
                return getLogger(key.split('.')[0], filename=key)
    return logger

def getActiveRequest():
    if not HELPER_CACHE.get_request:
        mw = importlib.import_module("rest.middleware")
        HELPER_CACHE.get_request = mw.get_request
    return HELPER_CACHE.get_request()

def log_print(*args):
    getLoggerByRequest(getActiveRequest()).info(*args)


def getLogRequestHeader(request):
    extra = []
    if bool(request):
        if hasattr(request, "ip"):
            extra.append(request.ip)
        extra.append(request.build_absolute_uri())
        if hasattr(request, "member") and request.member:
            extra.append("user: {}".format(request.member.username))
        if hasattr(request, "DATA"):
            extra.append(request.DATA.asDict())
    return extra


def log_exception(*args):
    request = getActiveRequest()
    extra = getLogRequestHeader(request)
    ERROR_LOGGER.exception(*extra, *args)
    getLoggerByRequest(request).exception(*extra, *args)


def log_error(*args):
    request = getActiveRequest()
    extra = getLogRequestHeader(request)
    ERROR_LOGGER.error(*extra, *args)
    getLoggerByRequest(request).error(*extra, *args)


def setLogModel(self, component, pk):
    # this method allows for updating the component to associate a log with
    if not pk or (self._log_pk == pk):
        return
    self._log_component = component
    self._log_pk = pk
    if hasattr(self, "request_log"):
        self.request_log.component = component
        self.request_log.pkey = pk
        self.request_log.save()
        

def getHostname():
    try:
        return os.uname()[1]
    except:
        pass
    return "unknown"

def getUsername():
    return getpass.getuser()

class TemporaryDirectory(object):
    """Context manager for tempfile.mkdtemp() so it's usable with "with" statement."""
    def __enter__(self):
        self.name = tempfile.mkdtemp()
        return self.name

    def __exit__(self, exc_type, exc_value, traceback):
        shutil.rmtree(self.name)

class TemporaryFile(object):
    def __init__(self, suffix=".tmp"):
        temp_file = tempfile.NamedTemporaryFile(delete=False,   suffix=suffix)
        self.name = temp_file.name

    def delete(self):
        os.remove(self.name)

    def __enter__(self):
        return self.name

    def __exit__(self, type, value, traceback):
        self.delete()

# Some mobile browsers which look like desktop browsers.
RE_MOBILE = re.compile(r"(iphone|ipod|blackberry|android|palm|windows\s+ce)", re.I)
RE_DESKTOP = re.compile(r"(windows|linux|os\s+[x9]|solaris|bsd)", re.I)
RE_BOT = re.compile(r"(spider|crawl|slurp|bot)", re.I)
RE_SOCIAL = re.compile(r"(facebookexternalhit/[0-9]|LinkedInBot|Twitterbot|Pinterest|Google.*snippet)", re.I)
RE_SCRAPERS = re.compile(r"(FlipboardProxy|Slurp|PaperLiBot|TweetmemeBot|MetaURI|Embedly)", re.I)

RE_EMAIL = re.compile(r"[^@]+@[^@]+\.[^@]+", re.I)

DEBUG_DATETIME = False
if hasattr(settings, "DEBUG_DATETIME"):
        DEBUG_DATETIME = getattr(settings, "DEBUG_DATETIME")

def graphBuilderInplace(part, field, graph):
    output = []
    if part not in graph:
        return output
    graph_part = graph[part]
    for f in graph_part:
        if type(f) is tuple:
            f1, f2 = f
            output.append(("{0}.{1}", "{2}").format(field, f1, f2))
        else:
            output.append("{0}.{1}".format(field, f))
    return output


def graphBuilder(root_graph, field, graph):
    for part in ["fields", "recurse_into"]:
        if part not in graph:
            continue
        graph_part = graph[part]
        if part not in root_graph:
            root_graph[part] = []
        root_part = root_graph[part]
        for f in graph_part:
            if type(f) is tuple:
                f1, f2 = f
                root_part.append(("{0}.{1}".format(field, f1), f2))
            else:
                root_part.append("{0}.{1}".format(field, f))
    return root_graph

def fuzzyMatch(a, b):
    if fuzz:
        if a and b:
            a = a.lower()
            b = b.lower()
            return max(fuzz.token_set_ratio(a,b),fuzz.partial_ratio(a,b))
        return 0
    print("MISSING FUZZWUZZY MODULE")
    return 100

def isValidEmail(email):
    return bool(RE_EMAIL.search(email))

def getProtocol(request):
    if request.is_secure():
        return "https://"
    return "http://"

def getSocialReferer(request):
    referer = getReferer(request)
    if referer and "://" in referer:
        r = referer.split("/")
        domain = r[2]
        if domain in ["t.co", "twitter.com"]:
            return "twitter"
        elif domain in ["facebook.com", "m.facebook.com"]:
            return "facebook"
        elif domain in ["linkedin.com", "lnkd.in"]:
            return "linkedin"
        elif domain in ["pinterest.com"]:
            return "pinterest"
        elif domain in ["plus.google.com", "plus.url.google.com"]:
            return "googleplus"
        elif domain in ["www.google.com"]:
            return "google"
        elif domain in ["bing.com", "www.bing.com"]:
            return "bing"
        return domain
    return referer

def getReferer(request):
    return request.META.get('HTTP_REFERER')

def getRemoteIP(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def getUserAgent(request):
  # Some mobile browsers put the User-Agent in a HTTP-X header
  return request.META.get('HTTP_X_OPERAMINI_PHONE_UA') or \
         request.META.get('HTTP_X_SKYFIRE_PHONE') or \
         request.META.get('HTTP_USER_AGENT', '')

def getSocialAgent(request):
    user_agent = getUserAgent(request).lower()
    if "facebook" in user_agent:
        return "facebook"
    if "linkedin" in user_agent:
        return "linkedin"
    if "twitter" in user_agent:
        return "twitter"
    if "pinterest" in user_agent:
        return "pinterest"
    if "google" in user_agent:
        return "google"
    if "yahoo" in user_agent:
        return "yahoo"
    if "flipboard" in user_agent:
        return "flipboard"
    if "embedly" in user_agent:
        return "embedly"
    return "unknown"

def agentHas(request, keyword):
    return keyword.lower() in getUserAgent(request).lower()

def isSocialScraper(request):
    user_agent = getUserAgent(request)
    return bool(RE_SCRAPERS.search(user_agent))

def isSocialAgent(request):
    user_agent = getUserAgent(request)
    return bool(RE_SOCIAL.search(user_agent))

def isBotAgent(request):
    user_agent = getUserAgent(request)
    return bool(RE_BOT.search(user_agent))

def isMobile(request):
    user_agent = getUserAgent(request)
    return bool(RE_MOBILE.search(user_agent)) and not bool(RE_BOT.search(user_agent))

def isDesktopAgent(request):
    user_agent = getUserAgent(request)
    return not bool(RE_MOBILE.search(user_agent)) and bool(RE_DESKTOP.search(user_agent)) or bool(RE_BOT.search(user_agent))

def lowerKeys(x):
    if isinstance(x, list):
        return [lowerKeys(v) for v in x]
    elif isinstance(x, dict):
        return dict((k.lower(), lowerKeys(v)) for k, v in list(x.items()))
    return x

def mergeDicts(*args):
    context = {}
    for arg in args:
        context.update(arg)
    return context

def removeUnderscoreKeys(x):
    if isinstance(x, list):
        return [removeUnderscoreKeys(v) for v in x]
    elif isinstance(x, dict):
        return dict((k.replace('_', ''), removeUnderscoreKeys(v)) for k, v in list(x.items()))
    return x

def filterByDateRange(qset, request=None, start=None, kind=None, eod=None, field="created", end=None, zone=None):
    """
    "DateRangeStart": POSIX Start Date,
    "DateRangeEnd": POSIX End Date,
    "DateRangeEOD": Specify the UTC end of day for the range
    "DateRangeField": "created or modified",
    "DateRangeKind": "none, day, month, year",
    """
    if request:
        field = request.DATA.get(["daterangefield", "datefield"], field)
        # print(("field is: {}".format(field)))

        day = request.DATA.get("dateday", None)
        month = request.DATA.get("datemonth", None)
        year = request.DATA.get("dateyear", None)
        if day or month or year:
            # print(("running by day, month, year for field: {}".format(field)))
            qf = {}
            if day:
                qf["{}__day".format(field)] = day
            if month:
                qf["{}__month".format(field)] = month
            if year:
                qf["{}__year".format(field)] = year
            # print(qf)
            return qset.filter(**qf)

        start = request.DATA.get(["daterangestart", "date_start"], start)
        if not start:
            return qset
        start = parseDate(start)
        # print(("start is: {}".format(start)))
        zone = request.DATA.get("daterangezone", zone)
        eod = request.DATA.get("daterangeeod", eod, field_type=int)
        if eod == -1:
            zone = None
            eod = None
        elif eod is None and request.group:
            zone = request.group.timezone
            eod = request.group.getEOD(onday=start, in_local=True)
        elif eod is None:
            eod = 0
        end = request.DATA.get(["daterangeend", "date_end"], end)
        if end is None:
            end = start + timedelta(days=1)
        else:
            end = parseDate(end)

        if end <= start:
            end = start + timedelta(days=1)

        fields = request.DATA.get("daterangefields", None, field_type=list)
        if fields:
            start_field = fields[0]
            stop_field = fields[1]
            if start.hour == 0:
                # this is a hack on a straight date, lets move zone to 8 hours
                start = start - timedelta(hours=8)
            qf = {"{0}__lte".format(start_field):start, "{0}__gte".format(stop_field):start}
            return qset.filter(**qf)
        kind = request.DATA.get(["date_kind"], kind)
        # print "kind is: {}".format(kind)
        # zone = request.DATA.get("daterangezone", zone)
        # print "zone is: {}".format(zone)
        # print "eod is: {}".format(eod)
        # # print eod
        start, end = getDateRange(start=start, end=end, kind=kind, eod=eod, zone=zone)
        # print start
        # print end
    else:
        start, end = getDateRange(start=start, end=None, kind=kind, eod=eod, zone=zone)
        # print start
        # print end

    if not field:
        field = "created"

    qf = {"{0}__gte".format(field):start, "{0}__lt".format(field):end}
    return qset.filter(**qf)




def diffMinutes(t1, t2):
    diff = t1 - t2
    days, seconds = diff.days, diff.seconds
    hours = (days * 24)
    return (seconds * 60) + (hours / 60)

def diffHours(t1, t2):
    diff = t1 - t2
    days, seconds = diff.days, diff.seconds
    hours = (days * 24)
    minutes = seconds * 60
    return (minutes * 60) + hours

def getContext(request, *args, **kwargs):
    version = settings.VERSION
    if settings.DEBUG:
        version = "{0}.{1}".format(version, time.time())

    c = {
        "version":version,
        "SITE_LABEL":settings.SITE_LABEL,
        "SITE_LOGO":settings.SITE_LOGO,
        "SERVER_NAME":settings.SERVER_NAME,
        "BASE_URL":settings.BASE_URL
    }

    if request:
        c["protocol"] = getProtocol(request)
        c["request"] = request

    for k, v in list(kwargs.items()):
        c[k] = v
    return c

def getAppNames():
    from django.apps import apps
    return [app_config.name for app_config in apps.get_app_configs()]

def getAllModels(app_name=None):
    from django.apps import apps
    if not app_name:
        return apps.get_models()
    return apps.get_app_config(app_name).get_models()


def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start


def getSetting(key, default=None):
    if hasattr(settings, key):
        return getattr(settings, key)
    return default

def filterByDates(qset, start=None, end=None, date_field="created"):
    q = {}
    if start:
        q["{}__gte".format(date_field)] = start

    if end:
        q["{}__lte".format(date_field)] = end
    if q:
        return qset.filter(**q)
    return qset

def getAverage(qset, field_name):
    res = qset.aggregate(avg_result=Avg(field_name))
    if "avg_result" in res and res["avg_result"] != None:
        return res["avg_result"]
    return 0.0

def getMin(qset, field_name):
    res = qset.aggregate(min_result=Min(field_name))
    if "min_result" in res and res["min_result"] != None:
        return res["min_result"]
    return 0.0

def getMax(qset, field_name):
    res = qset.aggregate(max_result=Max(field_name))
    if "max_result" in res and res["max_result"] != None:
        return res["max_result"]
    return 0.0

def getSum(qset, *args):
    params = {}
    for field_name in args:
        key = "sum_{}".format(field_name)
        params[key] = Sum(field_name)
    # print params
    res = qset.aggregate(**params)
    results = UberDict()
    for field_name in args:
        key = "sum_{}".format(field_name)
        value = res.get(key, 0)
        if value is None:
            value = 0
        results[field_name] = value
    if len(args) == 1:
        return list(results.values())[0]
    return results


def countOccurences(qset, field_name):
    output = UberDict()
    for item in list(qset.values(field_name).annotate(count=Count(field_name))):
        output[item[field_name]] = item["count"]
    return output


def filterOR(qset, *args):
    # filterOR(qset, dict(key1=val1), dict(key2=val2))
    q = Q(**args[0])
    for arg in args[1:]:
        q = q | Q(**arg)
    if not isinstance(qset, QuerySet):
        return qset.objects.filter(q)
    return qset.filter(q)

def updateModelFromDict(model, data):
    for key in data:
        setattr(model, key, data[key])
    return model

_KEY_NOTFOUND = object()

def getValueForKeys(data, key, default=None):
    # helper method for getting first key value from list
    if type(key) is list:
        for k in key:
            v = getValueForKeys(data, k, _KEY_NOTFOUND)
            if v != _KEY_NOTFOUND:
                return v
        return default

    if "." in key:
        keys = key.split('.')
        for k in keys:
            data = getValueForKeys(data, k, _KEY_NOTFOUND)
            if data is _KEY_NOTFOUND:
                return default
        return data

    if data is None:
        return None
    return data.get(key, default)

def dictToString(d, no_truncate=False):
    from io import StringIO
    output = StringIO()
    prettyWrite(d, output, no_truncate=no_truncate)
    out = output.getvalue()
    output.close()
    return out

def prettyPrint(d, f=sys.stdout, indent=4, banner=None):
    return prettyWrite(d, f, indent, banner)


try:
    import phonenumbers
except:
    phonenumbers = None

def isPhone(value):
    try:
        int(value.replace('-', '').replace('.', '').replace(' ', ''))
        return True
    except:
        pass
    return False

def normalizePhone(value):
    if phonenumbers:
        try:
            x = phonenumbers.parse(value, "US")
        except:
            print(value)
            x = phonenumbers.parse(value, None)
        return phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    return value.replace(' ', '').replace('.', '-').replace('(', '').replace(')', '-')


from decimal import Decimal
PRETTY_INDENT = 2
PRETTY_MAX_VALUE_LENGTH = 200
PRETTY_MAX_LINES = 400
PRETTY_MAX_LENGTH = 9000

def prettyWrite(d, f=None, indent=PRETTY_INDENT, banner=None, line_count=0, no_truncate=False):
    std_output = False
    if f is None:
        std_output = True
        f = StringIO()

    prev = None
    if banner:
        f.write('---- BEGIN {} ----\n'.format(banner))
    if type(d) is list:
        prev = False
        f.write('[')
        for i in d:
            if prev:
                line_count += 1
                f.write(',\n')
            else:
                line_count += 1
                f.write('\n')

            pos = 0
            if hasattr(f, "len"):
                pos = f.len

            if not no_truncate and (line_count > PRETTY_MAX_LINES or pos >= PRETTY_MAX_LENGTH):
                f.write('{}"...truncated"'.format(' ' * indent))
                break
            prev = True
            if type(i) is bool:
                i = int(i)
            if type(i) in [str, str]:
                if not no_truncate and len(i) >= PRETTY_MAX_VALUE_LENGTH:
                    f.write('{}"{}...truncated"'.format(' ' * indent, i[:PRETTY_MAX_VALUE_LENGTH-20]))
                else:
                    f.write('{}"{}"'.format(' ' * indent, i))
            elif type(i) is list or isinstance(i, dict):
                f.write(' ' * (indent))
                line_count = prettyWrite(i, f, indent+PRETTY_INDENT, line_count=line_count)
            elif type(i) is Decimal:
                f.write('{}{}'.format(' ' * indent, str(i)))
            else:
                f.write('{}"{}"'.format(' ' * indent, i))
        line_count += 1
        f.write('\n')
        f.write(' ' * (indent-PRETTY_INDENT))
        f.write(']')
    elif isinstance(d, dict):
        f.write('{')
        for key, value in list(d.items()):
            if prev:
                line_count += 1
                f.write(',\n')
            else:
                line_count += 1
                f.write('\n')

            pos = 0
            if hasattr(f, "len"):
                pos = f.len

            depth = indent / PRETTY_INDENT
            if not no_truncate and  (depth > 1 and (line_count > PRETTY_MAX_LINES or pos >= PRETTY_MAX_LENGTH)):
                f.write('{}"truncated":"...truncated"\n'.format(' ' * indent))
                break
            prev = True
            if type(key) in [str, str]:
                f.write('{}"{}":'.format(' ' * indent, key))
            else:
                f.write('{}{}: '.format(' ' * indent, str(key)))
            if type(value) is list or isinstance(value, dict):
                f.write(' ')
                line_count = prettyWrite(value, f, indent+PRETTY_INDENT, line_count=line_count)
            else:
                if type(value) in [str, str]:
                    if not no_truncate and len(value) >= PRETTY_MAX_VALUE_LENGTH:
                        f.write(' "{}...truncated"'.format(value[:PRETTY_MAX_VALUE_LENGTH-20]))
                    else:
                        f.write(' "{}"'.format(value))
                elif type(value) in [datetime, time]:
                    f.write(' "{}"'.format(value))
                elif type(value) is Decimal:
                    f.write(' {}'.format(str(value)))
                else:
                    f.write(' {}'.format(value))
        line_count += 1
        f.write('\n')
        f.write(' ' * (indent-PRETTY_INDENT))
        f.write('}')
    else:
        f.write(str(d))

    if banner:
        f.write('\n---- END {} ----\n'.format(banner))
    if indent == PRETTY_INDENT:
        f.write("\n")
    if std_output:
        sys.stdout.write(f.getvalue())
        f.close()
    return line_count

def randomKey(count=6):
    return ''.join(random.choice(string.uppercase + string.digits) for x in range(count))

def getStackString():
    import traceback
    return str(traceback.format_exc())

def isPidRunning(pid):
    if sys.platform.startswith("linux"):
        return os.path.exists("/proc/{}".format(pid))
    try:
        os.kill(pid, 0)  # or signal.SIGKILL
    except OSError as err:
        return False
    return True

def getPidFromFile(pid_file):
    pid = 0
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            pid = f.read()
            if pid.isdigit():
                pid = int(pid)
    return pid

def sudoCMD(cmd, as_user=None, test_first=True):
    if as_user and as_user == getUsername():
        sudo_cmd = []
        if isinstance(cmd, list):
            sudo_cmd.extend(cmd)
        else:
            sudo_cmd.append(cmd)
        return subprocess.Popen(sudo_cmd, close_fds=True)

    test_sudo_cmd = ["sudo", "-lU", as_user]
    sudo_cmd = ["sudo", "-u", as_user]
    if as_user:
        test_sudo_cmd.append("-lU")
        test_sudo_cmd.append(as_user)
        sudo_cmd.append("-u")
        sudo_cmd.append(as_user)

    if isinstance(cmd, list):
        test_sudo_cmd.extend(cmd)
        sudo_cmd.extend(cmd)
    else:
        test_sudo_cmd.append(cmd)
        sudo_cmd.append(cmd)

    if test_first:
        process = subprocess.Popen(test_sudo_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if err.strip():
            raise Exception("WARNING: cannot run {}, we don't have sudo rights".format(test_sudo_cmd))
    return subprocess.Popen(sudo_cmd, close_fds=True)

def toString(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value

def toBytes(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    elif isinstance(value, bytearray):
        value = bytes(value)
    return value

def toByteArray(value):
    if isinstance(value, bytearray):
        return value
    elif isinstance(value, str):
        return bytearray(value, 'utf-8')
    elif isinstance(value, bytes):
        return bytearray(value)
    return value

def toHex(value):
    return toBytes(value).hex().upper()

def hexToByteArray(value):
    return bytearray.fromhex(value)

def hexToString(value):
    return bytes.fromhex(value).decode('utf-8')

def toBase64(value):
    return base64.b64encode(value)

def fromBase64(value):
    return toString(base64.b64decode(value))

