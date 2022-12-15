from rest import helpers as rh
from rest import views as rv
from rest.log import getLogger
from .models import Bounce, Complaint, Message
from . import mailtils
import requests

logger = getLogger("inbox", filename="inbox.log")


def on_email(request, data):
    logger.info("debug", data)
    if data.content is None:
        logger.error("message has no content", data)
        return rv.restStatus(request, False)
    msg_data = mailtils.parseRawMessage(data.content)
    logger.info("parsed", msg_data)
    # msg = Message(
    #     sent_at=msg_data.sent_at,
    #     subject=msg_data.subject,
    #     message=msg_data.message,
    #     html=msg_data.html,
    #     body=msg_data.body,
    #     to=msg_data.to,
    #     cc=msg_data.cc,
    #     from_email=msg_data.from_email,
    #     from_name=msg_data.from_name)
    # msg.save()
    return rv.restStatus(request, True)


def on_subscriptionconfirmation(request, msg):
    rh.log_print("subcribed to", msg)
    url = msg.SubscribeURL
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


def on_unknown(request, msg):
    logger.error("unknown email", msg)
    return rv.restStatus(request, False)


SES_HANDLERS = {
    "email": on_email,
    "SubscriptionConfirmation": on_subscriptionconfirmation,
    "Bounce": on_bounce,
    "Complaint": on_complaint
}


