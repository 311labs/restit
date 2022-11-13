import sys

from functools import wraps
from django.urls import URLResolver
from django.urls import re_path
from django.shortcuts import Http404
from django.http import HttpResponseRedirect
from django.utils.cache import patch_cache_control, add_never_cache_headers, patch_vary_headers

from django.conf import settings
from rest.views import restStatus
from rest.models import RestError, requestHasPerms, PermisionDeniedException
from rest import helpers

from account.models import Member

from datetime import datetime
from auditlog.models import PersistentLog

import importlib
import threading
import traceback


# background task (no return)
def rest_async(func):
    """
    Execute the function asynchronously in a separate thread
    """
    @wraps(func)
    def inner(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
    return inner


def postpone(function):
    def decorator(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
    return decorator


#
# Annotate a view with the URL that points to it
#
def rest_error_catcher(func, request, *args, **kwargs):
    try:
        return func(request, *args, **kwargs)
    except PermisionDeniedException as err:
        helpers.log_error("permission denied {} for {}:{}".format(request.user, request.method, request.path))
        return restStatus(request, False, error=err.reason, error_code=err.code)
    except RestError as err:
        helpers.log_exception(err.reason)
        return restStatus(request, False, error=err.reason, error_code=err.code)
    except Exception as err:
        # TODO email errors to admins
        helpers.log_exception(request.path)
        stack = str(traceback.format_exc())
        host = request.get_host()
        server = getattr(settings, "HOSTNAME", "unknown")
        try:
            body = request.body.decode('utf-8')
        except Exception:
            body = request.DATA.asDict()

        PersistentLog.logException(body, request=request, component="rest", action="error")
        if hasattr(settings, "NOTIFY_REST_ERRORS") and settings.NOTIFY_REST_ERRORS:
            subject = "REST Error: {} - {}".format(host, str(err))
            # hide sensative data in body
            # ebody = body
            # if not getattr(settings, "DEBUG", False):
            #     ebody = "-- protected: see audit log --"
            context = {
                "to": settings.NOTIFY_REST_ERRORS,
                # "request": request,
                "method": str(request.method),
                "path": str(request.path),
                "host": host,
                "server": server,
                "subject": subject,
                "error": str(err),
                "stack": str(stack),
                "user": str(request.user),
                # "body": ebody,
                # "meta": request.META,
                "params": request.DATA.asDict()
            }

            # try:
            Member.notifyWithPermission(
                "rest_errors", subject, template="email/error.html", context=context, email_only=True)
        return restStatus(request, False, error=str(err), stack=stack)
    return restStatus(request, False)


def dispatcher(request, *args, **kwargs):
    module = kwargs.pop('__MODULE')
    pattern = kwargs.pop('__PATTERN')
    method = request.method
    if request.method == 'HEAD':
        method = 'GET'
    key = pattern + '__' + method
    if key in module.urlpattern_methods:
        return rest_error_catcher(module.urlpattern_methods[key], request, *args, **kwargs)
    method = "ALL"
    key = pattern + '__' + method
    if key in module.urlpattern_methods:
        return rest_error_catcher(module.urlpattern_methods[key], request, *args, **kwargs)
    # print module.urlpattern_methods
    return restStatus(request, False, error="endpoint not found", error_code=404)


def _url_method(pattern, method=None, *args, **kwargs):
    """
    Register a view handler for a specific HTTP method
    """
    caller_filename = sys._getframe(2).f_code.co_filename
    module = None
    for m in list(sys.modules.values()):
        if m and '__file__' in m.__dict__ and m.__file__ is not None and m.__file__.startswith(caller_filename):
            module = m
            break

    def _wrapper(f):
        new_pattern = True
        if module:
            rpc_root_module = module
            if module.__name__.count('.') > 1:
                # this means we are not in root
                # print module.__name__
                root_name = module.__name__.split('.')[0]
                # print "importing {0}.rpc".format(root_name)
                rpc_root_module = importlib.import_module(root_name + ".rpc")
            # print "{0}/{1}".format(rpc_root_module.__name__, pattern)
            elif not module.__name__.endswith(".rpc") and module.__name__.count('.'):
                # print module.__name__
                root_name = module.__name__.split('.')[0]
                # print "importing {0}.rpc".format(root_name)
                rpc_root_module = importlib.import_module(root_name + ".rpc")
            lmethod = method
            if lmethod is None:
                lmethod = "ALL"
            if 'urlpatterns' not in rpc_root_module.__dict__:
                rpc_root_module.urlpatterns = []
            if lmethod and 'urlpattern_methods' not in rpc_root_module.__dict__:
                rpc_root_module.urlpattern_methods = {}
            elif lmethod and pattern + '__' in rpc_root_module.urlpattern_methods:
                new_pattern = False

            if lmethod:
                rpc_root_module.urlpattern_methods[pattern + '__' + lmethod] = f

            if new_pattern:
                if lmethod:
                    func = dispatcher
                    func.csrf_exempt = True
                    rpc_root_module.urlpattern_methods[pattern + '__'] = True
                    if 'kwargs' not in kwargs:
                        kwargs['kwargs'] = {}
                    kwargs['kwargs']['__MODULE'] = rpc_root_module
                    kwargs['kwargs']['__PATTERN'] = pattern
                else:
                    func = f
                if type(pattern) not in [str, str]:
                    helpers.log_print("NOT A STRING", pattern)
                rpc_root_module.urlpatterns += [re_path(pattern, func, *args, **kwargs)]
            f.__url__ = (lmethod, pattern)
            f.csrf_exempt = True
        return f
    _wrapper.caller_filename = "{0}/{1}".format(module.__name__, pattern)
    return _wrapper


def url(pattern, *args, **kwargs):
    """
    Usage:
    @url(r'^users$')
    def get_user_list(request):
        ...
    """
    return _url_method(pattern, *args, **kwargs)


def urlGET(pattern, *args, **kwargs):
    """
    Register GET handler for url pattern
    """
    return _url_method(pattern, 'GET', *args, **kwargs)


def urlPUT(pattern, *args, **kwargs):
    """
    Register PUT handler for url pattern
    """
    return _url_method(pattern, 'PUT', *args, **kwargs)


def urlPOST(pattern, *args, **kwargs):
    """
    Register POST handler for url pattern
    """
    return _url_method(pattern, 'POST', *args, **kwargs)


def urlPOST_NOCSRF(pattern, *args, **kwargs):
    """
    Register POST handler for url pattern
    """
    return _url_method(pattern, 'POST', *args, **kwargs)


def urlDELETE(pattern, *args, **kwargs):
    """
    Register DELETE handler for url pattern
    """
    return _url_method(pattern, 'DELETE', *args, **kwargs)


#
# Continue the @url decorator pattern into sub-modules, if desired
#

def include_urlpatterns(regex, module):
    """
    Usage:

    # in top-level module code:
    urlpatterns = include_urlpatterns(r'^profile/', 'apps.myapp.views.profile')
    """
    return [URLResolver(regex, module)]


#
# patched django decorators check if return is httpresponse
#
def cache_control(**kwargs):
    def _cache_controller(view_func):
        @wraps(view_func)
        def _cache_controlled(request, *args, **kw):
            response = view_func(request, *args, **kw)
            if hasattr(response, 'has_header'):  # check if response is httpresponse
                patch_cache_control(response, **kwargs)
            return response
        return _cache_controlled
    return _cache_controller


def never_cache(view_func):
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        if hasattr(response, 'has_header'):  # check if response is httpresponse
            add_never_cache_headers(response)
        return response
    return _wrapped_view_func


def vary_on_headers(*headers):
    def decorator(func):
        @wraps(func)
        def inner_func(*args, **kwargs):
            response = func(*args, **kwargs)
            if hasattr(response, 'has_header'):  # check if response is httpresponse
                patch_vary_headers(response, headers)
            return response
        return inner_func
    return decorator


def vary_on_cookie(func):
    @wraps(func)
    def inner_func(*args, **kwargs):
        response = func(*args, **kwargs)
        if hasattr(response, 'has_header'):  # check if response is httpresponse
            patch_vary_headers(response, ('Cookie',))
        return response
    return inner_func


def force_ssl(func):
    @wraps(func)
    def inner_func(request=None, *args, **kwargs):
        if (not settings.DEBUG) and request and not request.is_secure():
            url = request.build_absolute_uri()
            return HttpResponseRedirect(url.replace('http://', 'https://'))

        response = func(request, *args, **kwargs)
        return response
    return inner_func


def login_required(func):
    @wraps(func)
    def inner_func(request=None, *args, **kwargs):
        if not request.user.is_authenticated:
            return restStatus(request, False, error="permission denied", error_code=401)
        return rest_error_catcher(func, request, *args, **kwargs)
    return inner_func


def login_optional(func):
    @wraps(func)
    def inner_func(request=None, *args, **kwargs):
        return rest_error_catcher(func, request, *args, **kwargs)
    return inner_func


def staff_required(func):
    @wraps(func)
    def inner_func(request=None, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return restStatus(request, False, error="staff request denied", error_code=402)
        return rest_error_catcher(func, request, *args, **kwargs)
    return inner_func


class perm_required(object):
    def __init__(self, perms):
        self.perms = perms

    def __call__(self, func):
        def inner_func(request=None, *args, **kwargs):
            status, error, code = requestHasPerms(request, self.perms)
            if not status:
                return restStatus(request, False, error=error, error_code=code)
            return rest_error_catcher(func, request, *args, **kwargs)
        return inner_func


class post_perm_required(object):
    def __init__(self, perms):
        self.perms = perms

    def __call__(self, func):
        def inner_func(request=None, *args, **kwargs):
            if request.method == "post":
                status, error, code = requestHasPerms(request, self.perms)
                if not status:
                    return restStatus(request, False, error=error, error_code=code)
            elif not request.user.is_authenticated:
                return restStatus(request, False, error="permission denied", error_code=401)
            return rest_error_catcher(func, request, *args, **kwargs)
        return inner_func


def ip_whitelist(func, *args, **kwargs):
    @wraps(func)
    def inner_func(request=None, *args, **kwargs):
        request_ip = request.META['REMOTE_ADDR']
        if request_ip not in settings.AUTHORIZED_IPS:
            return restStatus(request, False, error="permission denied")
        return rest_error_catcher(func, request, *args, **kwargs)
    return inner_func


def periodicCheckListHas(list_obj, has_value):
    if type(list_obj) is list:
        return has_value in list_obj
    return list_obj == has_value


PERIODIC_FUNCS = []
PERIODIC_EVERY_5_MINUTES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
PERIODIC_EVERY_10_MINUTES = [0, 10, 20, 30, 40, 50]
PERIODIC_EVERY_15_MINUTES = [0, 15, 30, 45]
PERIODIC_EVERY_15_MINUTES_2 = [5, 20, 35, 50]
PERIODIC_EVERY_20_MINUTES = [5, 25, 45]
PERIODIC_EVERY_30_MINUTES = [15, 45]


def periodic(minute=None, hour=None, day=None, month=None, weekday=None, tz=None):
    """
    supports minute=5 or minute=[5,10,20]
    """
    def decorator(func):
        PERIODIC_FUNCS.append({
            "func": func,
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "weekday": weekday,
            "tz": tz
        })

        @wraps(func)
        def inner_func(force=False, verbose=False, now=None):
            if now is None:
                now = datetime.now()
            if force:
                return func(force, verbose, now)
            if tz:
                now = helpers.convertToLocalTime(tz, now)
            # lets create our when
            if minute is not None and not periodicCheckListHas(minute, now.minute):
                return -22
            if hour is not None and not periodicCheckListHas(hour, now.hour):
                return -22
            if day is not None and not periodicCheckListHas(day, now.day):
                return -22
            if month is not None and not periodicCheckListHas(month, now.month):
                return -22
            if weekday is not None and not periodicCheckListHas(weekday, now.weekday()):
                return -22
            return func(force, verbose, now)
        inner_func.is_periodic = True
        return inner_func
    return decorator

