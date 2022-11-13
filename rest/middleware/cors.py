from django import http
from django.conf import settings
from urllib.parse import urlparse
from django.utils.cache import patch_vary_headers

if hasattr(settings, "CORS_SHARING_ALLOWED_ORIGINS"):
    CORS_SHARING_ALLOWED_ORIGINS = settings.CORS_SHARING_ALLOWED_ORIGINS
else:
    CORS_SHARING_ALLOWED_ORIGINS = '*'

if hasattr(settings, "CORS_SHARING_ALLOWED_METHODS"):
    CORS_SHARING_ALLOWED_METHODS = settings.CORS_SHARING_ALLOWED_METHODS
else:
    CORS_SHARING_ALLOWED_METHODS = ['POST', 'GET', 'OPTIONS', 'PUT', 'DELETE']

if hasattr(settings, "CORS_SHARING_ALLOWED_HEADERS"):
    CORS_SHARING_ALLOWED_HEADERS = settings.CORS_SHARING_ALLOWED_HEADERS
else:
    CORS_SHARING_ALLOWED_HEADERS = [
        'accept',
        'accept-encoding',
        'authorization',
        'content-type',
        'dnt',
        'origin',
        'user-agent',
        'x-authtoken',
        'x-csrftoken',
        'x-sessionid',
        'x-requested-with']

CORS_ALLOW_CREDENTIALS = getattr(settings, "CORS_ALLOW_CREDENTIALS", True)


class CorsMiddleware(object):
    """
        This middleware allows cross-domain XHR using the html5 postMessage API.

        Access-Control-Allow-Origin: http://foo.example
        Access-Control-Allow-Methods: POST, GET, OPTIONS, PUT, DELETE
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # rest_helpers.log_print(dict(request.META))
        # check if preflight header, then return HTTP 200
        if request.method.lower() == "options" and 'HTTP_ACCESS_CONTROL_REQUEST_METHOD' in request.META:
            response = http.HttpResponse()
        else:
            response = self.get_response(request)
        response = self.updateResponse(request, response)
        # rest_helpers.log_print(response._headers)
        return response

    def getAllowedOrigin(self, request):
        origin = request.META.get('HTTP_ORIGIN', None)
        if origin:
            if CORS_SHARING_ALLOWED_ORIGINS == '*':
                return origin
            host = urlparse(origin)
            if 'localhost' in host:
                host = 'localhost'
            if type(CORS_SHARING_ALLOWED_ORIGINS) is list:
                if host in CORS_SHARING_ALLOWED_ORIGINS:
                    return origin
            elif type(CORS_SHARING_ALLOWED_ORIGINS) in [str, str]:
                if host == CORS_SHARING_ALLOWED_ORIGINS:
                    return origin

        host = request.META.get('HTTP_HOST', None)
        if not host:
            return None
        return "https://{}".format(host)

    def updateResponse(self, request, response):
        # rest_helpers.log_print("CORS: updating response")
        if CORS_ALLOW_CREDENTIALS:
            response['Access-Control-Allow-Credentials'] = 'true'
        else:
            response['Access-Control-Allow-Credentials'] = 'false'

        allowed_origin = self.getAllowedOrigin(request)
        if allowed_origin:
            # rest_helpers.log_print('Access-Control-Allow-Origin: {}'.format(allowed_origin))
            response['Access-Control-Allow-Origin']  = allowed_origin
            patch_vary_headers(response, ['Origin'])

        if request.method.lower() == "options":
            response['Access-Control-Allow-Headers'] = ",".join( CORS_SHARING_ALLOWED_HEADERS )
            response['Access-Control-Allow-Methods'] = ",".join( CORS_SHARING_ALLOWED_METHODS )
            response["Access-Control-Max-Age"] = "7200"
        return response

