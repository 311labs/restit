from rest import decorators as rd
from rest import views as rv
from rest import helpers as rh
from . import models as mailbox
from .handlers import SES_HANDLERS


@rd.url(r'^mailbox$')
@rd.url(r'^mailbox/(?P<pk>\d+)$')
def rest_on_mailbox(request, pk=None):
    return mailbox.Message.on_rest_request(request, pk)


@rd.urlPOST(r'^ses/incoming$')
def rest_on_ses_incoming(request):
    msg_type = request.DATA.get("Type")
    handler = SES_HANDLERS.get(msg_type, None)
    if not handler:
        rh.log_error("rest_on_ses_incoming", request.DATA.toDict())
        return rv.restStatus(request, False)
    return handler(request)
