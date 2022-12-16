
import os
import threading
from io import StringIO
import csv
import mimetypes
import boto3

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

try:
    from inlinestyler.utils import inline_css
except Exception:
    inline_css = None

from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.conf import settings

import metrics
from rest.uberdict import UberDict
from rest.middleware import get_request
from rest.log import getLogger

EMAIL_LOGGER = getLogger("email", filename="email.log")
# ses settings
SES_ACCESS_KEY = getattr(settings, "SES_ACCESS_KEY", None)
SES_SECRET_KEY = getattr(settings, "SES_SECRET_KEY", None)
SES_REGION = getattr(settings, "SES_REGION", None)
EMAIL_METRICS = getattr(settings, "EMAIL_METRICS", False)


def send(to, subject, body=None, attachments=[], 
         from_email=settings.DEFAULT_FROM_EMAIL,
         fail_silently=True, template=None, 
         context=None, do_async=False, replyto=None):
    # make sure to is list
    if not isinstance(to, (tuple, list)):
        to = [to]
    # if template lets render
    if isinstance(body, (tuple, list)):
        text, html = body
    else:
        text = None
        html = body

    if template:
        html = renderBody(html, template, context)

    msg = createMultiPartMessage(
        settings.DEFAULT_FROM_EMAIL, to, subject,
        text=text, html=html, attachments=attachments,
        replyto=replyto)

    # send now or async
    if not do_async:
        return sendMail(msg, from_email, to, fail_silently=fail_silently)
    else:
        t = threading.Thread(target=sendMail, args=[msg, from_email, to])
        t.start()
    return True


def renderBody(body, template=None, context=None):
    if template and body and not context:
        context = {
            "body": body
        }

    if template and context:
        if isinstance(context, dict):
            context['settings'] = settings
        if template[-4:] not in ["html", ".txt"]:
            template += ".html"
        body = render_to_string(template, context)
        if inline_css:
            body = inline_css(body)
    return body


def createMultiPartMessage(sender, recipients, subject, text, html, attachments, replyto):
    """
    Creates a MIME multipart message object.
    Uses only the Python `email` standard library.
    Emails, both sender and recipients, can be just the email string or have the format 'The Name <the_email@host.com>'.

    :param sender: The sender.
    :param recipients: List of recipients. Needs to be a list, even if only one recipient.
    :param subject: The subject of the email.
    :param text: The text version of the email body (optional).
    :param html: The html version of the email body (optional).
    :param attachments: List of files to attach in the email.
    :param replyto: optional reply to address.
    :return: A `MIMEMultipart` to be used to send the email.
    """
    multipart_content_subtype = 'alternative' if text and html else 'mixed'
    msg = MIMEMultipart(multipart_content_subtype)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    if replyto:
        msg.add_header('reply-to', replyto)

    # Record the MIME types of both parts - text/plain and text/html.
    # According to RFC 2046, the last part of a multipart message, in this case the HTML message, is best and preferred.
    if text:
        part = MIMEText(text, 'plain')
        msg.attach(part)
    if html:
        # HACK to remove codec errors
        html = html.encode('ascii', 'ignore').decode('ascii')
        part = MIMEText(html, 'html')
        msg.attach(part)

    # Add attachments
    index = 0
    for atch in attachments or []:
        if isinstance(atch, (str, bytes)):
            index += 1
            atch = UberDict(name="attachment{}.txt".format(index), data=atch, mimetype="text/plain")
        # lets attach it
        part = MIMEApplication(atch.data)
        part.add_header('Content-Type', atch.mimetype)
        part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(atch.name))
        msg.attach(part)
    return msg


def sendMail(msg, sender, recipients, fail_silently=True):
    try:
        ses_client = getSES(SES_ACCESS_KEY, SES_SECRET_KEY, SES_REGION)
        ses_client.send_raw_email(
            Source=sender,
            Destinations=recipients,
            RawMessage={'Data': msg.as_string()}
        )
        if EMAIL_METRICS:
            metrics.metric("emails_sent", category="email", min_granularity="hourly")
        return True
    except Exception as err:
        if EMAIL_METRICS:
            metrics.metric("email_errors", category="email", min_granularity="hourly")
        EMAIL_LOGGER.exception(err)
        EMAIL_LOGGER.error(msg.as_string())
        if not fail_silently:
            raise err
    return False


def makeAttachment(filename, data):
    atment = UberDict(name=filename, data=data)
    atment.mimetype, junk = mimetypes.MimeTypes().guess_type(filename)
    return atment


def getSES(access_key, secret_key, region):
    return boto3.client(
        'ses',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region)


def generateCSV(qset, fields, name):
    a = UberDict()
    a.name = name
    a.file = StringIO.StringIO()
    csvwriter = csv.writer(a.file)
    csvwriter.writerow(fields)

    for row in qset.values_list(*fields):
        row = [str(x) for x in row]
        csvwriter.writerow(row)
    a.data = a.file.getvalue()
    a.mimetype = "text/csv"
    return a


def render_to_mail(name, context):
    if not context.get("request"):
        context["request"] = get_request()
    context['newline'] = "\n"
    toaddrs = None
    if 'to' in context:
        toaddrs = context['to']
        if type(toaddrs) != list:
            toaddrs = [toaddrs]
    else:
        try:
            toaddrs = render_to_string(name + ".to", context).splitlines()
        except TemplateDoesNotExist:
            return
    try:
        while True:
            toaddrs.remove('')
    except ValueError:
        pass
    if len(toaddrs) == 0:
        EMAIL_LOGGER.error("Sending email to no one: {}".format(name), context)
        return

    try:
        html_content = render_to_string(name + ".html", context)
        if inline_css:
            html_content = inline_css(html_content)
    except TemplateDoesNotExist:
        html_content = None
        pass

    text_content = ""
    try:
        text_content = render_to_string(name + ".txt", context)
    except TemplateDoesNotExist:
        if html_content is not None:
            raise TemplateDoesNotExist("requires at least one content template")

    if 'from' in context:
        fromaddr = context['from']
    else:
        try:
            fromaddr = render_to_string(name + ".from", context).rstrip()
        except TemplateDoesNotExist:
            fromaddr = settings.DEFAULT_FROM_EMAIL
    # print fromaddr
    if 'subject' in context:
        subject = context['subject']
    else:
        try:
            subject = render_to_string(name + ".subject", context).rstrip()
        except TemplateDoesNotExist:
            EMAIL_LOGGER.error("Sending email without subject: %s" % name)
            return False
    replyto = None
    if "replyto" in context:
        replyto = context["replyto"]

    body = None
    if bool(text_content) and bool(html_content):
        body = (text_content, html_content)
    elif bool(text_content):
        body = text_content
    elif bool(html_content):
        body = html_content

    send(toaddrs, subject, body=body, from_email=fromaddr, do_async=True, replyto=replyto)


