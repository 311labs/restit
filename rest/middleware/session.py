from importlib import import_module
from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date
from rest import ua
from rest import helpers
import time

# HACK FOR SameSite
from http.cookies import Morsel
Morsel._reserved['samesite'] = 'SameSite'
SESSION_COOKIE_SAMESITE = getattr(settings, "SESSION_COOKIE_SAMESITE", None)


class SimpleSessionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def __call__(self, request):
        try:
            self.process_request(request)
            response = self.get_response(request)
            self.process_response(request, response)
        except Exception:
            helpers.log_exception()
        return response

    def process_request(self, request):
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        request.session = self.SessionStore(session_key)
        # helpers.log_error("session keys", session_key, request.session.session_key)

    def process_response(self, request, response):
        if response.status_code == 500:
            return response
        # print("saving session: \n{}".format(request.session.session_key))
        # print("session cooking domain: {}".format(settings.SESSION_COOKIE_DOMAIN))
        # print("session cooking path: {}".format(settings.SESSION_COOKIE_PATH))
        # print("session max_age: {}".format(max_age))
        expires = None
        max_age = None
        request.session.save()
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        if session_key == request.session.session_key:
            return response
        # helpers.log_error("new session keys", request.session.session_key)
        if request.session.accessed: 
            patch_vary_headers(response, ('Cookie',))
        response.set_cookie(
            settings.SESSION_COOKIE_NAME,
            request.session.session_key, max_age=max_age,
            expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
            path=settings.SESSION_COOKIE_PATH,
            secure=settings.SESSION_COOKIE_SECURE or None,
            httponly=settings.SESSION_COOKIE_HTTPONLY or None)
        if SESSION_COOKIE_SAMESITE:
            # now lets verify browser supports it
            ua_info = ua.parse(request.META.get('HTTP_USER_AGENT', ''))
            family = ua_info.get("user_agent.family", None)
            if not family:
                return response

            major = ua_info.get("user_agent.major", 0)
            if bool(major):
                major = int(major)
            if family.lower() == "chrome" and major < 75:
                return response
            elif family.lower() == "firefox" and major < 60:
                return response
            elif family.lower() == "safari" and major < 12:
                return response     
            elif family.lower() == "ie" and major < 16:
                return response                       
            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"] = SESSION_COOKIE_SAMESITE
        return response


class SessionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def __call__(self, request):
        self.process_request(request)
        response = self.get_response(request)
        self.process_response(request, response)
        return response

    def process_request(self, request):
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        # for key in request.COOKIES:
        #     print("cookie.{} = {}".format(key, request.COOKIES.get(key)))
        # # print(session_key)
        # print("session key: {}".format(session_key))
        # print("session SESSION_COOKIE_NAME: {}".format(settings.SESSION_COOKIE_NAME))

        secure_keys = getattr(settings, "SESSION_KEY_SECURE", True)
        if not secure_keys:
            if not session_key:
                session_key = request.META.get('HTTP_AUTHORIZATION', None)
                if session_key and session_key.count(" ") > 0:
                    # this is not a session key
                    session_key = None

            if not session_key:
                session_key = request.META.get('HTTP_X_SESSIONID', None)

            if not session_key:
                session_key = request.POST.get('SESSION_KEY', None)

            if not session_key:
                session_key = request.GET.get('SESSION_KEY', None)

        if session_key:
            request.session = self.SessionStore(session_key)
            if not request.session.exists(session_key):
                session_key = None
        request.session = self.SessionStore(session_key)
        # check if session key is dead?
        # print(request.session)

    def process_response(self, request, response):
        """
        If request.session was modified, or if the configuration is to save the
        session every time, save the changes and set a session cookie or delete
        the session cookie if the session has been emptied.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError as err:
            # print("session attribute error: {}".format(str(err)))
            pass
        else:
            # First check if we need to delete this cookie.
            # The session should be deleted only if the session is entirely empty
            if settings.SESSION_COOKIE_NAME in request.COOKIES and empty:
                response.delete_cookie(
                    settings.SESSION_COOKIE_NAME,
                    domain=settings.SESSION_COOKIE_DOMAIN)
            else:
                if accessed:
                    patch_vary_headers(response, ('Cookie',))
                if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                    if request.session.get_expire_at_browser_close():
                        max_age = None
                        expires = None
                    else:
                        max_age = request.session.get_expiry_age()
                        expires_time = time.time() + max_age
                        expires = http_date(expires_time)
                    # Save the session data and refresh the client cookie.
                    # Skip session save for 500 responses, refs #3881.
                    if response.status_code != 500:
                        # print("saving session: \n{}".format(request.session.session_key))
                        # print("session cooking domain: {}".format(settings.SESSION_COOKIE_DOMAIN))
                        # print("session cooking path: {}".format(settings.SESSION_COOKIE_PATH))
                        # print("session max_age: {}".format(max_age))
                        request.session.save()
                        response.set_cookie(
                            settings.SESSION_COOKIE_NAME,
                            request.session.session_key, max_age=max_age,
                            expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                            path=settings.SESSION_COOKIE_PATH,
                            secure=settings.SESSION_COOKIE_SECURE or None,
                            httponly=settings.SESSION_COOKIE_HTTPONLY or None)
                        if SESSION_COOKIE_SAMESITE:
                            # now lets verify browser supports it
                            ua_info = ua.parse(request.META.get('HTTP_USER_AGENT', ''))
                            family = ua_info.get("user_agent.family", None)
                            if not family:
                                return response
                            major = int(ua_info.get("user_agent.major", 0))
                            if family.lower() == "chrome" and major < 75:
                                return response
                            elif family.lower() == "firefox" and major < 60:
                                return response
                            elif family.lower() == "safari" and major < 12:
                                return response     
                            elif family.lower() == "ie" and major < 16:
                                return response                       
                            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"] = SESSION_COOKIE_SAMESITE
        return response


