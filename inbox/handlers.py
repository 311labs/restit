from rest import helpers as rh
from rest import views as rv
from rest.log import getLogger
from .models import Bounce, Complaint, Message, Attachment
from . import mailtils
import requests
from objict import objict


logger = getLogger("inbox", filename="inbox.log")


def on_subscriptionconfirmation(request):
    rh.log_print("subcribed to", request.DATA.asDict())
    url = request.DATA.get("SubscribeURL", None)
    resp = requests.get(url)
    return rv.restStatus(request, True)


def on_bounce(request, msg):
    if not msg.bounce or not isinstance(msg.bounce.bouncedRecipients, list):
        logger.error("invalid bounce request")
        return rv.restStatus(request, True)
    for who in msg.bounce.bouncedRecipients:
        # kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None
        Bounce.log(
            kind="email",
            address=who.emailAddress,
            reason=who.diagnosticCode,
            reporter=msg.bounce.reportingMTA,
            code=who.status,
            source=msg.mail.source,
            source_ip=msg.mail.sourceIp)
    return rv.restStatus(request, True)


def on_complaint(request, msg):
    if not msg.bounce or not isinstance(msg.bounce.bouncedRecipients, list):
        logger.error("invalid bounce request")
        return rv.restStatus(request, True)
    for who in msg.complaint.complainedRecipients:
        # kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None
        Complaint.log(
            kind="email",
            address=who.emailAddress,
            reason=msg.complaint.complaintFeedbackType,
            user_agent=msg.complaint.userAgent,
            source=msg.mail.source,
            source_ip=msg.mail.sourceIp)
    return rv.restStatus(request, True)


def on_email(request, msg):
    if msg.content is None:
        logger.error("message has no content", msg)
        return rv.restStatus(request, False)
    to_email = msg.receipt.recipients[0]
    msg_data = mailtils.parseRawMessage(msg.content)
    logger.info("parsed", msg_data)
    msg = Message(
        to_email=to_email,
        sent_at=msg_data.sent_at,
        subject=msg_data.subject,
        message=msg_data.message,
        html=msg_data.html,
        body=msg_data.body,
        to=msg_data.to,
        cc=msg_data.cc,
        from_email=msg_data.from_email,
        from_name=msg_data.from_name)
    msg.save()

    for msg_atch in msg_data.attachments:
        atch = Attachment(message=msg, name=msg_atch.name)
        if msg_atch.encoding == "base64":
            atch.saveMediaFile(msg_atch.payload, "media", msg_atch.name, is_base64=True)
        elif msg_atch.encoding == "quoted-printable":
            obj = mailtils.toFileObject(msg_atch)
            atch.saveMediaFile(obj, "media", msg_atch.name)
    return rv.restStatus(request, True)


def on_notification(request):
    msg = objict.fromJSON(request.DATA.get("Message", ""))
    rh.log_print("on_notification", msg)
    handler = SES_HANDLERS.get(msg.notificationType, None)
    if handler is None:
        rh.log_error(f"no handler for {msg.notificationType}")
        return rv.restStatus(request, False)
    return handler(request, msg)


def on_unknown(request):
    return rv.restStatus(request, False)


SES_HANDLERS = {
    "SubscriptionConfirmation": on_subscriptionconfirmation,
    "Bounce": on_bounce,
    "Complaint": on_complaint,
    "Notification": on_notification,
    "Received": on_email
}


