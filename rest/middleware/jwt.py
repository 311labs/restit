from django.conf import settings
from django.apps import apps
from rest import helpers

from account.models.session import AuthSession
from rest.jwtoken import JWToken, JWT_KEY

# HACK FOR SameSite
from django.utils.cache import patch_vary_headers
from http.cookies import Morsel
Morsel._reserved['samesite'] = 'SameSite'

JWT_COOKIE_KEY = getattr(settings, "JWT_COOKIE_KEY", "JWT_TOKEN")
JWT_ALLOW_COOKIE = getattr(settings, "JWT_ALLOW_COOKIE", False)


class JWTokenMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clear_jwt_cookie = False
        self.process_request(request)
        response = self.get_response(request)
        self.process_response(request, response)
        return response

    def process_request(self, request):
        request.jwt = None
        request.token = None
        request.token_bearer = None
        request.device_id = None
        request.auth_model = None
        request.ip = helpers.getRemoteIP(request)
        token = request.META.get('HTTP_AUTHORIZATION', "").strip()
        if token.count(" ") != 1:
            self.process_cookie(request)
            return
        # helpers.log_error("token auth in progress", token)
        request.token_bearer, request.token = token.split(' ')
        request.member = None
        if request.token_bearer.lower() == "bearer":
            self.process_jwt(request)
        elif request.token_bearer.lower() == "authtoken":
            self.process_authtoken(request)
        if request.member is not None:
            request.member.touchActivity()

    def process_cookie(self, request):
        if not JWT_ALLOW_COOKIE:
            return
        token = request.COOKIES.get(JWT_COOKIE_KEY, None)
        if token is not None:
            # helpers.log_error("cookie found")
            request.token = token
            request.token_bearer = "bearer"
            self.process_jwt(request)
            if request.token is None:
                # invalid JWT let us delete cookie
                # tells middleware to delete cookie in response
                request.clear_jwt_cookie = True

    def process_jwt(self, request):
        # this is JWT so let us authenticate
        token = JWToken(request.token)
        if token.payload is None:
            helpers.log_error("invalid jwt token", request.token)
            request.token = None
            request.token_bearer = None
            return
        User = apps.get_model("account", "User")
        user = User.objects.filter(pk=token.payload.user_id).last()
        if user is None:
            helpers.log_error("invalid jwt user", request.token)
            request.token = None
            request.token_bearer = None
            return
        member = user.getMember()
        if member.security_token is None:
            member.security_token = JWT_KEY
            member.save()
        # set the token key to the member security token, this lets us invalidate tokens
        token.key = member.security_token
        if not token.is_valid:
            helpers.log_error("invalid jwt", request.token)
            request.token = None
            request.token_bearer = None
            return
        if not token.isExpired():
            helpers.log_error("expired jwt", request.token)
            request.token = None
            request.token_bearer = None
            return
        if not member.canLogin(request, False):
            helpers.log_error("user cannot login via jwt", request.token)
            request.token = None
            request.token_bearer = None
            return
        request.jwt = token
        request.user = user
        request.member = member
        request.signature = token.session_id
        request.device_id = token.payload.device_id
        request.auth_session = AuthSession.GetSession(request)

    def process_authtoken(self, request):
        AuthToken = apps.get_model("account", "AuthToken")
        atoken = AuthToken.objects.filter(token=request.token).last()
        if atoken is None:
            helpers.log_error("login failed with authtoken")
            return
        if not atoken.member.canLogin(request, False):
            helpers.log_error("user cannot login via authtoken", request.token)
            return 
        request.user = atoken.member.getUser()
        request.signature = atoken.signature
        request.member = atoken.member
        request.token_bearer = "auth_token"

    def process_response(self, request, response):
        if not JWT_ALLOW_COOKIE:
            return
        if request.token_bearer and request.token_bearer.lower() == "bearer":
            cookie_token = request.COOKIES.get(JWT_COOKIE_KEY, None)
            if cookie_token != request.token:
                # this is a new authed jwt token, store it in the cookie
                # patch_vary_headers(response, ('Cookie',))
                response.set_cookie(
                    key=JWT_COOKIE_KEY,
                    value=request.token,
                    secure=False,
                    httponly=False,
                    max_age=86400)
                response.cookies[JWT_COOKIE_KEY]["samesite"] = "Lax"
        elif request.clear_jwt_cookie:
            response.delete_cookie(JWT_COOKIE_KEY)

