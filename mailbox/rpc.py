from rest import decorators as rd
from rest import views as rv
from . import models as mailbox
from .handlers import SES_HANDLERS


@rd.url(r'^mailbox$')
@rd.url(r'^mailbox/(?P<pk>\d+)$')
def rest_on_mailbox(request, pk=None):
    return mailbox.Message.on_rest_request(request, pk)


@rd.urlGET(r'^mailbox/ses/incoming$')
def rest_on_ses_incoming(request):
    msg = request.DATA.asUberDict()
    handler = SES_HANDLERS.get(msg.sns_type, None)
    if not handler:
        return rv.restStatus(request, False)
    return handler(request, msg)
