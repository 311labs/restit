from rest import helpers
from rest import UberDict
from rest.requestex import RequestData
from django import http
from django.conf import settings

from threading import currentThread
import types

_requests = {}


def get_request():
    i = currentThread().ident
    if i in _requests:
        return _requests[i]
    return None


class GlobalRequestMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        response = response or self.get_response(request)
        return response

    def _getReturnType(self, request):
        rtype = "text/plain"

        # figure return type
        if getattr(request, 'DATA', {}).get('_type', None):
            accept_list = [request.DATA.get('_type')]
        elif 'HTTP_ACCEPT' in getattr(request, 'META', {}):
            accept_list = request.META["HTTP_ACCEPT"].split(',')
        else:
            accept_list = []

        for i in range(len(accept_list)):
            a2 = accept_list[i].split(";", 1)
            if len(a2) == 2:
                accept_list[i] = a2[0]

        ext = "json"
        if 'application/json' in accept_list:
            rtype = "application/json"
        else:
            rtype = "text/plain"
        return rtype

    def process_exception(self, request, exception):
        helpers.log_exception()
        rtype = self._getReturnType(request)
        payload = UberDict(error=str(exception) or getattr(type(exception), '__name__'), status=500)
        if type(exception) == http.Http404:
            payload.status = 404
        return http.HttpResponse(payload.toJSON(), status=200, content_type=rtype)

    def process_locale(self, request):
        locale = settings.DEFAULT_LANGUAGE
        if request.method == "POST":
            data = request.POST
        else:
            data = request.GET

        if "lang" in data:
            locale = data.get("lang")
        elif "locale" in data:
            locale = data.get("locale")
        elif 'HTTP_ACCEPT_LANGUAGE' in request.META:
            locale = request.META['HTTP_ACCEPT_LANGUAGE']

        lang = [x.strip()[:2] for x in locale.split(',')]
        if len(lang):
            request.LANGUAGE_CODE = lang[0]
        else:
            # we do this for when we get bad values above like empty strings
            request.LANGUAGE_CODE = settings.DEFAULT_LANGUAGE

        if "-" in request.LANGUAGE_CODE:
            request.COUNTRY_CODE = request.LANGUAGE_CODE.split('-')[0]
        else:
            request.COUNTRY_CODE = request.LANGUAGE_CODE

    def process_request(self, request):
        _requests[currentThread().ident] = request
        request.ip = helpers.getRemoteIP(request)
        # print "IP: " + request.ip
        request.setLogModel = types.MethodType(helpers.setLogModel, request)
        request._log_component = None
        request._log_pk = None
        request.logger = helpers.getLoggerByRequest(request)
        if not hasattr(request, "member"):
            request.member = None
        if not hasattr(request, "group"):
            request.group = None
        try:
            RequestData.upgradeRequest(request)
            if request.user.is_authenticated:
                if request.member is None:
                    request.member = request.user.getMember()
                if request.group is None:
                    gid = request.DATA.get(["group_id", "group"])
                    if gid:
                        request.group = request.member.getGroup(gid)
                if request.member is not None:
                    request.member.touchActivity()
        except Exception as err:
            helpers.log_exception("GlobalRequestMiddleware")
            print((str(err)))

        if settings.PROCESS_LOCALE:
            self.process_locale(request)
