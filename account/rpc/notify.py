from rest import decorators as rd
from rest import views as rv
from rest import models as rm
from account import models as am
import requests

@rd.url(r'^email/bounced/$')
@rd.url(r'^email/bounced/(?P<pk>\d+)$')
@rd.login_required
def handleBounced(request, pk=None):
    return am.BounceHistory.on_rest_request(request, pk)


@rd.url(r'^notifications/$')
@rd.url(r'^notifications/(?P<pk>\d+)$')
@rd.perm_required("manage_users")
def handleNotifications(request, pk=None):
    return am.NotificationRecord.on_rest_request(request, pk)


# BEGIN AWS SNS HANDLER

EMAIL_MODEL_CACHE = {}

def handleBounce(request):
    msg = request.DATA.asUberDict()
    if not msg.bounce or not isinstance(msg.bounce.bouncedRecipients, list):
        return rv.restStatus(request, True)

    for who in msg.bounce.bouncedRecipients:
        # kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None
        am.BounceHistory.log(
            kind="email",
            address=who.emailAddress,
            reason=who.diagnosticCode,
            reporter=msg.bounce.reportingMTA,
            code=who.status,
            source=msg.mail.source,
            source_ip=msg.mail.sourceIp)
    return rv.restStatus(request, True)

def getEmailHandler(name):
    if name in EMAIL_MODEL_CACHE:
        return EMAIL_MODEL_CACHE[name]
    a_name, m_name = name.split(".")
    model = rm.RestModel.getModel(a_name, m_name)
    EMAIL_MODEL_CACHE[name] = model
    return model

def onValidEmail(msg):
    handlers = EMAIL_MODEL_HANDLERS.get(msg.to.lower(), None)
    if not handlers:
        return False
    if isinstance(handlers, list):
        for name in handlers:
            handler = getEmailHandler(name)
            if handler and hasattr(handler, "on_email"):
                handler.on_email(msg)
    else:
        handler = getEmailHandler(handlers)
        if handler and hasattr(handler, "on_email"):
            handler.on_email(msg)

@rd.url(r'^aws/sns$')
@rd.url(r'^aws/sns/$')
def email_handler(request):
    if not request.is_sns:
        print((request.META))
        print((request.body))
        return rv.restStatus(request, False, error="invalid type")

    if request.sns_type == "Bounce":
        return handleBounce(request)

    if request.sns_type == "SubscriptionConfirmation":
        url = request.DATA.get("SubscribeURL")
        res = requests.get(url)
        return rv.restStatus(request, True)

    if request.sns_type == "email":
        source = request.DATA.get("mail.source")
        # this is a list
        destination = request.DATA.get("mail.destination")
        subject = request.DATA.get("mail.commonHeaders.subject")
        content = request.DATA.get("content")
        if content:
            try:
                msg = mailman.parse_raw_message(content)
                # print("begin email")
                # print(msg)
                # print("end email")
                onValidEmail(UberDict.fromdict(msg))
                # parseTicketEmail(msg)
            except Exception as err:
                stack = str(traceback.format_exc())
                Member.notifyWithPermission("rest_errors", "error: {}\n<br>{}\n<br>\n{}".format(str(err), stack, content), context={}, email_only=True)
    print(("sns_type = {}".format(request.sns_type)))
    return rv.restStatus(request, True)

