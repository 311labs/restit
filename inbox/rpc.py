from rest import decorators as rd
from rest import views as rv
from rest import helpers as rh
from . import models as inbox
from .handlers import SES_HANDLERS


@rd.url(r'^inbox$')
@rd.url(r'^inbox/(?P<pk>\d+)$')
@rd.login_required
def rest_inbox(request, pk=None):
    return inbox.Mailbox.on_rest_request(request, pk)


@rd.url(r'^message$')
@rd.url(r'^message/(?P<pk>\d+)$')
@rd.login_required
def rest_message(request, pk=None):
    return inbox.Message.on_rest_request(request, pk)


@rd.url(r'^message/attachment$')
@rd.url(r'^message/attachment/(?P<pk>\d+)$')
@rd.login_required
def rest_attachment(request, pk=None):
    return inbox.Attachment.on_rest_request(request, pk)


@rd.url(r'^bounced$')
@rd.url(r'^bounced/(?P<pk>\d+)$')
@rd.login_required
def rest_bounced(request, pk=None):
    return inbox.Bounce.on_rest_request(request, pk)


@rd.url(r'^complaint$')
@rd.url(r'^complaint/(?P<pk>\d+)$')
@rd.login_required
def rest_complaint(request, pk=None):
    return inbox.Complaint.on_rest_request(request, pk)


@rd.urlPOST(r'^ses/incoming$')
def rest_ses_incoming(request):
    msg_type = request.DATA.get("Type")
    handler = SES_HANDLERS.get(msg_type, None)
    if not handler:
        rh.log_error("rest_on_ses_incoming", request.DATA.toDict())
        return rv.restStatus(request, False)
    return handler(request)
