from django.db import models
from django.conf import settings
from django.http import HttpResponse

from telephony.models import SMS, PhonenumberInfo

from rest import helpers
from rest.views import *
from rest.decorators import *
import importlib

try:
    from twilio.twiml.messaging_response import MessagingResponse
except ImportError:
    pass


@url(r'^sms/msg$')
@url(r'^sms/msg/(?P<pk>\d+)$')
@perm_required("view_logs")
def handle_sms_list(request, pk=None):
    return SMS.on_rest_request(request, pk)


@urlPOST(r'^sms$')
@urlPOST(r'^sms/$')
@login_required
def sendSMS(request):
    me = request.member
    group = request.group
    # for now you can only send msgs to a member
    if "to" in request.DATA:
        to = request.DATA.getlist("to")
        members = Member.objects.filter(pk__in=to)
        message = request.DATA.get("message")
        return restGet(request, SMS.broadcast(members, message, by=me, group=group, transport="sms"))

    if "message" not in request.DATA:
        return restStatus(request, False, error="permission denied")

    member = Member.getFromRequest(request)
    if not member:
        return restStatus(request, False, error="requires valid member")
    phone = member.getProperty("phone")
    if not phone:
        return restStatus(request, False, error="member has no phone number")
    message = request.DATA.get("message")
    # send(endpoint, message, by=None, group=None, to=None, transport="sms", srcpoint=None):
    return restGet(request, SMS.send(phone, message, me, group, member))


@urlPOST(r'^sms/incoming$')
def receiveSMS(request):
    helpers.log_print(request.DATA.asDict())
    SMS.log_incoming(request)
    from_number = request.DATA.get("From")
    handler_name = settings.TELEPHONY_HANDLERS.get(from_number, None)
    if handler_name is not None:
        model = importlib.import_module(handler_name)
        msg = model.on_sms(request)
        if msg is not None:
            resp = MessagingResponse()
            resp.message(msg)
            return HttpResponse(resp.to_xml(), content_type='text/xml')
    resp = MessagingResponse()
    resp.message(settings.TELEPHONY_DEFAULT_SMS_RESPONSE)
    return HttpResponse(resp.to_xml(), content_type='text/xml')


@url(r'^info$')
@url(r'^info/(?P<pk>\d+)$')
@login_required
def handle_info(request, pk=None):
    return PhonenumberInfo.on_rest_request(request, pk)


@url(r'^lookup$')
@login_required
def handle_lookup(request, pk=None):
    number = request.DATA.get(["number", "phone"])
    if number is None:
        return restPermissionDenied(request)
    info = PhonenumberInfo.lookup(number)
    return info.restGet(request)




