from rest import helpers as rh
from rest import views as rv
from rest.log import getLogger
from rest import settings
from taskqueue.models import Task
from medialib.stores import s3store
from .models import Bounce, Complaint, Message, Attachment, Mailbox
from . import mailtils
import metrics

import requests
from objict import objict


logger = getLogger("inbox", filename="inbox.log")


def on_subscriptionconfirmation(request):
    logger.info("subcribed to", request.DATA.asDict())
    url = request.DATA.get("SubscribeURL", None)
    resp = requests.get(url)
    return rv.restStatus(request, True)


def on_bounce(request, msg):
    if not msg.bounce or not isinstance(msg.bounce.bouncedRecipients, list):
        logger.error("invalid bounce request")
        return rv.restStatus(request, True)
    for who in msg.bounce.bouncedRecipients:
        # kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None
        metrics.metric("emails_bounced", category="email", min_granularity="hourly")
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
        metrics.metric("emails_complaints", category="email", min_granularity="hourly")
        Complaint.log(
            kind="email",
            address=who.emailAddress,
            reason=msg.complaint.complaintFeedbackType,
            user_agent=msg.complaint.userAgent,
            source=msg.mail.source,
            source_ip=msg.mail.sourceIp)
    return rv.restStatus(request, True)


def on_email(request, msg):
    """
    Email receiving can be configured in 2 ways.
     1. raw email via SNS which would have content field
     2. s3 bucket stored email which will have a receipt.action.bucketName
    """
    if msg.content is None and msg.receipt and msg.receipt.action:
        action = msg.receipt.action
        if action.type == "S3":
            return on_s3_email(request, msg, action.bucket, action.objectKey)

    if msg.content is None:
        logger.error("message has no content", msg)
        return rv.restStatus(request, False)

    msg_data = mailtils.parseRawMessage(msg.content)
    return on_raw_email(request, msg, msg_data)


def on_s3_email(request, msg, bucket_name, object_key):
    msg_data = mailtils.parseRawMessage(s3store.getObjectContent(bucket_name, object_key))
    return on_raw_email(request, msg, msg_data)
   

def on_raw_email(request, msg, msg_data):
    to_email = msg.receipt.recipients[0]
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
    metrics.metric("emails_received", category="email", min_granularity="hourly")

    for msg_atch in msg_data.attachments:
        atch = Attachment(message=msg, name=msg_atch.name)
        if msg_atch.encoding == "base64":
            atch.saveMediaFile(msg_atch.payload, "media", msg_atch.name, is_base64=True)
        elif msg_atch.encoding == "quoted-printable":
            obj = mailtils.toFileObject(msg_atch)
            atch.saveMediaFile(obj, "media", msg_atch.name)
        atch.save()

    # now lets find if a mailbox exists
    mailbox = Mailbox.objects.filter(email=to_email).last()
    if mailbox is not None:
        Task.Publish(
            mailbox.tq_app, mailbox.tq_handler,
            data=dict(pk=msg.pk, to_email=to_email, from_email=msg.from_email),
            channel=mailbox.tq_channel)

    return rv.restStatus(request, True)


def on_notification(request):
    msg = objict.fromJSON(request.DATA.get("Message", ""))
    handler = SES_HANDLERS.get(msg.notificationType, None)
    if handler is None:
        logger.error(f"no handler for {msg.notificationType}")
        return rv.restStatus(request, False)
    try:
        return handler(request, msg)
    except Exception:
        logger.exception()
    return rv.restStatus(request, False)


def on_unknown(request):
    return rv.restStatus(request, False)


SES_HANDLERS = {
    "SubscriptionConfirmation": on_subscriptionconfirmation,
    "Bounce": on_bounce,
    "Complaint": on_complaint,
    "Notification": on_notification,
    "Received": on_email
}


