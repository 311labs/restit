from sessionlog.models import SessionLog

from django.db import models
from django.conf import settings

import copy

from rest.models import RestModel
from rest import helpers
from rest.log import getLogger

import traceback

AUDIT_LOGGER = getLogger("auditlog", filename="auditlog.log")
AUDITLOG_LOGGER_BY_USER = getattr(settings, "AUDITLOG_LOGGER_BY_USER", False)
AUDITLOG_LOGGERS = getattr(settings, "AUDITLOG_LOGGERS", {})

PERSISTENT_LOG_PRINT = getattr(settings, "PERSISTENT_LOG_PRINT", False)


MAX_AUDIT_LINES = 400
MAX_AUDIT_LENGTH = 9000
MAX_AUDIT_LINE_LENGTH = 200


class ConsoleColors:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    PINK = "\033[35m"
    BLUE = '\033[34m'
    WHITE = '\033[37m'

    HBLACK = '\033[90m'
    HRED = '\033[91m'
    HGREEN = '\033[92m'
    HYELLOW = '\033[93m'
    HBLUE = '\033[94m'
    HPINK = "\033[95m"
    HWHITE = '\033[97m'

    HEADER = '\033[95m'
    FAIL = '\033[91m'
    OFF = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


LOG_FILTERS = getattr(settings, "AUDIT_LOG_FILTERS", {})


class PersistentLog(models.Model, RestModel):
    class RestMeta:
        DEFAULT_SORT = "-when"
        CAN_SAVE = False
        QUERY_FIELDS = ["level", "component", "pkey", "action", "request_method", "request_path", "tid", "group"]
        SEARCH_FIELDS = ["user__username", "user__last_name", "message", "session__ip", "request_path"]
        SEARCH_TERMS = [
            "message", "action", "component", "tid",
            "pkey", ("component_id", "pkey"),
            ("ip", "session__ip"),
            ("path", "request_path"),
            ("method"), "request_method",
            ("username", "user__username"),
            ("group", "group__pk"),
            ("country", "session__location__country"),
            ("state", "session__location__state"),
            ("country", "session__location__country")]
        DATE_RANGE_FIELD = "when"
        # number of days to go back (increase performance)
        DATE_RANGE_DEFAULT = 7

        FORMATS = {
            "csv": [
                "when",
                "level",
                "request_method",
                "request_path",
                "action",
                "message",
                "session.ip",
                "user.username",
                "group.name",
                "tid"
            ]
        }

        GRAPHS = {
            "default": {
                "graphs": {
                    "user": "default",
                    "group": "default",
                    "session": "default"
                }
            },
            "list": {
                "graphs": {
                    "user": "default",
                    "group": "default",
                    "session": "default"
                }
            }
        }

    when = models.DateTimeField(db_index=True, auto_now_add=True, editable=False, help_text="When change was logged")
    level = models.IntegerField(default=0)
    message = models.TextField(blank=True, null=True, default=None)

    action = models.TextField(max_length=127, blank=True, null=True, default=None, db_index=True)
    component = models.CharField(max_length=127, blank=True, null=True, default=None, db_index=True)
    pkey = models.IntegerField(blank=True, null=True, default=None, db_index=True)
    session = models.ForeignKey(SessionLog, null=True, blank=True, on_delete=models.CASCADE)
    request_method = models.CharField(max_length=254, blank=True, null=True, default=None)
    tid = models.CharField(max_length=254, blank=True, null=True, default=None, db_index=True)
    request_path = models.TextField(blank=True, null=True, default=None)
    user = models.ForeignKey("account.User", null=True, default=None, on_delete=models.CASCADE)
    group = models.ForeignKey("account.Group", null=True, default=None, on_delete=models.CASCADE)

    def setMessage(self, message, truncate=True, sanatize=True):
        if message is None:
            self.message = "None"
            return
        if isinstance(message, dict) or type(message) is list:
            if sanatize and isinstance(message, dict):
                message = PersistentLog.sanatize(message)
            self.message = helpers.dictToString(message, no_truncate=not truncate)
        else:
            self.message = helpers.toString(message)

        if truncate:
            if self.message.count('\n') > MAX_AUDIT_LINES:
                p = helpers.find_nth(self.message, '\n', MAX_AUDIT_LINES)
                self.message = self.message[:p]
                self.message += "\n ... <truncated lines>"

            if len(self.message) > MAX_AUDIT_LENGTH:
                lines = self.message.split('\n')
                tlines = []
                for ln in lines:
                    if len(ln) >= MAX_AUDIT_LINE_LENGTH:
                        tlines.append(ln[:MAX_AUDIT_LINE_LENGTH] + '...<truncated line len>')
                    else:
                        tlines.append(ln)
                self.message = '\n'.join(tlines)

        # check for invalid characters
        if self.message.find("\0") >= 0:
            self.message = self.message.replace("\0", "<null>")
            # helpers.log_error("found null characters", self.message)

    def printToLog(self):
        print_log = ["{}{}:{}{}".format(
            ConsoleColors.YELLOW, self.request_path, self.request_method, ConsoleColors.OFF)]
        if self.action == "request":
            print_log.append("{0}------- BEGIN --------------".format(ConsoleColors.YELLOW))
        print_log.append('{0}***** BEGIN {1}.{2} *****{3}'.format(
            ConsoleColors.YELLOW, self.component, self.action, ConsoleColors.HGREEN))
        if self.user and self.user.is_authenticated:
            print_log.append("USER: {}".format(self.user.username))
        if self.group:
            print_log.append("GROUP: {}".format(self.group.name))
        if self.tid:
            print_log.append("TID: {}".format(self.tid))
        if self.message:
            print_log.append(helpers.toString(self.message))
        else:
            print_log.append("no data")
        print_log.append('{0}***** END {1}.{2} *****{3}'.format(
            ConsoleColors.YELLOW, self.component, self.action, ConsoleColors.OFF))
        if self.action == "response":
            print_log.append("{}------- END {}:{}  --------------{}\n".format(
                ConsoleColors.YELLOW, self.request_path, self.request_method, ConsoleColors.OFF))
        if print_log:
            helpers.log_print(*print_log)

    @staticmethod
    def sanatize_password(value, n=1):
        if value is None or not isinstance(value, str):
            return value
        st = value
        return ''.join("*" if i % n == 0 else char for i, char in enumerate(st, 1))

    @staticmethod
    def sanatize_track(value):
        if value is None or not isinstance(value, str):
            return value
        st = value
        if len(st) > 12:
            pan = None
            pan2 = None
            parts = st.split('?')
            for p1 in parts:
                p1 = p1.upper().replace(';', '').replace('%B', '').replace('B', '')
                ex_data = None
                if '=' in p1:
                    pos = p1.find('=')
                    pan = p1[:pos]
                    ex_data = p1[pos + 8:]
                    st = st.replace(ex_data, "*" * len(ex_data))
                elif '^' in p1:
                    pan = p1[:p1.find('^')]
                    pos = p1.rfind('^')
                    ex_data = p1[pos + 8:]
                    st = st.replace(ex_data, "*" * len(ex_data))
                elif "D2" in p1:
                    p1 = p1.replace("D2", "=")
                    pos = p1.find('=')
                    pan = p1[:pos]
                    ex_data = p1[pos + 8:]
                    st = st.replace(ex_data, "*" * len(ex_data))
                else:
                    continue
                if not pan2:
                    pan2 = pan[:6] + "***" + pan[-4:]
            if pan is not None:
                return st.replace(pan, pan2)
        return value

    @staticmethod
    def sanatize_pan(value):
        if value and len(value) > 10:
            return "{}***{}".format(value[:6], value[-4:])
        return value

    @staticmethod
    def sanatize_epb(value):
        if isinstance(value, str):
            return "{}:*****".format(len(value))
        return value

    @staticmethod
    def sanatize_ssn(value):
        if value:
            return "***-**-{}".format(value[-4:])
        return value

    @staticmethod
    def sanatize_all(value):
        if isinstance(value, str):
            return "*" * len(value)
        return value

    @staticmethod
    def sanatize(obj):
        # deepcopy vs copy?
        sobj = copy.copy(obj)
        for key in sobj:
            lkey = key.lower()
            if lkey in LOG_FILTERS:
                funcn = LOG_FILTERS.get(lkey)
                if callable(funcn):
                    sobj[key] = funcn(sobj[key])
                elif hasattr(PersistentLog, funcn):
                    sobj[key] = getattr(PersistentLog, funcn)(sobj[key])
            elif lkey in ["pan", "cardnumber"]:
                sobj[key] = PersistentLog.sanatize_pan(sobj[key])
            elif "key" in lkey or lkey in ["5a", "57", "99"]:
                sobj[key] = PersistentLog.sanatize_all(sobj[key])
            elif lkey.startswith("track"):
                sobj[key] = PersistentLog.sanatize_track(sobj[key])
            elif "password" in lkey:
                sobj[key] = PersistentLog.sanatize_password(sobj[key])
            elif lkey == "epb":
                sobj[key] = PersistentLog.sanatize_epb(sobj[key])
            elif lkey == "ssn":
                sobj[key] = PersistentLog.sanatize_ssn(sobj[key])
            # lets truncate
            if type(sobj[key]) in [str, str] and len(sobj[key]) > MAX_AUDIT_LINE_LENGTH:
                sobj[key] = sobj[key][:MAX_AUDIT_LINE_LENGTH] + '...<truncated linelen>'
            if isinstance(sobj[key], dict):
                sobj[key] = PersistentLog.sanatize(sobj[key])
        return sobj

    @staticmethod
    def log(message, level=0, request=None, component=None,
            pkey=None, action=None, group=None, path=None, method=None, tid=None, no_truncate=False):
        plog = PersistentLog.createLogFromRequest(
            request, component=component, tid=tid, pkey=pkey, action=action, group=group,
            path=path, method=method, level=level)

        plog.setMessage(message, truncate=not no_truncate)

        try:
            plog.save()
        except Exception:
            helpers.log_exception(plog.message)

        if PERSISTENT_LOG_PRINT:
            plog.printToLog()
        return plog

    @staticmethod
    def logException(message=None, level=50, request=None, component=None,
                     pkey=None, action="error", group=None, path=None,
                     method=None, tid=None, no_truncate=True):
        # LETS LOG THE REQUEST DATA TO BE SURE
        if request is None:
            from rest.middleware import get_request
            request = get_request()

        helpers.log_exception(message)
        if request:
            helpers.log_error(request.DATA.toDict())
            # request.DATA.log()
            helpers.log_error("tid={}\npath={}\nip={}\nuser={}".format(
                tid, path, request.ip, request.user))

        # LOG THE EXCEPTION TO local LOGGERS
        plog = PersistentLog.createLogFromRequest(
            request=request, component=component, tid=tid, pkey=pkey, action=action, group=group,
            path=path, method=method, level=level)
        stack = str(traceback.format_exc())
        plog.setMessage(stack, truncate=not no_truncate)
        try:
            plog.save()
        except Exception:
            helpers.log_exception(plog.message)
        return plog

    @staticmethod
    def logError(message=None, level=0, request=None, component=None,
                 pkey=None, action="error", group=None, path=None,
                 method=None, tid=None, no_truncate=True):
        # LETS LOG THE REQUEST DATA TO BE SURE
        if request is None:
            from rest.middleware import get_request
            request = get_request()
        if request:
            request.DATA.log()
        plog = PersistentLog.createLogFromRequest(
            request, component=component, tid=tid, pkey=pkey, action=action, group=group,
            path=path, method=method, level=level)
        stack = str(traceback.format_exc())
        plog.setMessage(stack, truncate=not no_truncate)
        try:
            plog.save()
        except Exception:
            helpers.log_exception(plog.message)
        # print all errors to local logs
        plog.printToLog()
        return plog

    @staticmethod
    def createLogFromRequest(request=None, component=None, tid=None,
                             pkey=None, action=None, group=None,
                             path=None, method=None, level=10):
        if request is None:
            from rest.middleware import get_request
            request = get_request()
        if pkey is None and request is not None and hasattr(request, "_log_component"):
            if request._log_pk is not None:
                component = request._log_component
                pkey = request._log_pk
        plog = PersistentLog(
            group=group, level=level, component=component, tid=tid,
            pkey=pkey, action=action, request_path=path, request_method=method)
        if request:
            if request.user.is_authenticated:
                plog.user = request.user
            if not group and hasattr(request, "group"):
                plog.group = request.group
            if not path:
                plog.request_path = request.path
            else:
                plog.request_path = path
            if not method:
                plog.request_method = request.method
            else:
                plog.request_method = method
            plog.session = SessionLog.GetSession(request)
            if plog.tid is None:
                if hasattr(request, "terminal") and request.terminal:
                    plog.tid = request.terminal.tid
        return plog


class AuditLog(models.Model):
    """
    Audit Log
    """

    class Meta:
        permissions = (
            ("can_read", "Can read audit log"),
        )

    when = models.DateTimeField(auto_now_add=True, editable=False, help_text="When change was logged")
    model = models.CharField(max_length=127, db_index=True)
    pkey = models.IntegerField(db_index=True)
    attribute = models.CharField(max_length=127)
    user = models.ForeignKey("account.User", null=True, on_delete=models.CASCADE)
    session = models.ForeignKey(SessionLog, null=True, blank=True, on_delete=models.CASCADE)
    how = models.TextField(max_length=127, null=True, blank=True)
    referer = models.TextField(null=True, blank=True)
    stack = models.TextField(null=True, blank=True)
    oldval = models.TextField(null=True, blank=True)
    newval = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return "[%s] %s.%s" % (self.when, self.model, self.attribute)

    def reference(self):
        if self.referer:
            try:
                ret = self.referer.partition(settings.BASE_URL)
            except AttributeError:
                pass
            else:
                if ret[0] == '':
                    return ret[2]
            try:
                ret = self.referer.partition(settings.BASE_URL_SECURE)
            except AttributeError:
                pass
            else:
                if ret[0] == '':
                    return ret[2]

        try:
            return self.session.user_agent.partition(' ')[0]
        except (SessionLog.DoesNotExist, AttributeError):
            pass

        return None
