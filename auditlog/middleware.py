from django.conf import settings

DEBUG_REST_TERMINAL_ONLY = getattr(settings, "DEBUG_REST_TERMINAL_ONLY", False)
DEBUG_REST_INPUT = getattr(settings, "DEBUG_REST_INPUT", False)
DEBUG_REST_END_POINTS = getattr(settings, "DEBUG_REST_END_POINTS", [])


def checkRestDebug(request):
    for ep in DEBUG_REST_END_POINTS:
        if request.path.startswith(ep):
            return True
    return False


class LogRequest(object):
    last_request = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.process_request(request)

    def process_request(self, request):
        # LogRequest.last_request = request
        if request.path.startswith("/rpc/"):
            log_output = DEBUG_REST_INPUT or checkRestDebug(request)
            if DEBUG_REST_TERMINAL_ONLY:
                log_output = hasattr(request, "terminal") and request.terminal
            if log_output:
                request.DATA.log()
        response = self.get_response(request)
        return response

