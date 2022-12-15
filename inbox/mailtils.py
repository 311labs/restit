from io import StringIO
import email
from email.utils import parseaddr, parsedate_to_datetime, getaddresses
from email.header import decode_header

from objict import objict


def parseRawMessage(msgobj):
    """
    Parse the email and return a dictionary of relevant data.
    """
    if isinstance(msgobj, str):
        msgobj = email.message_from_string(msgobj)
    if msgobj['Subject'] is not None:
        decodefrag = decode_header(msgobj['Subject'])
        subj_fragments = []
        for s, enc in decodefrag:
            if enc:
                s = str(s, enc).encode('utf8', 'replace')
            subj_fragments.append(s)
        subject = ''.join(subj_fragments)
    else:
        subject = None
    attachments = []
    body = None
    html = None
    for part in msgobj.walk():
        attachment = parseAttachment(part)
        if attachment:
            attachments.append(attachment)
        elif part.get_content_type() == "text/plain":
            if body is None:
                body = ""
            try:
                body += str(
                    part.get_payload(decode=True),
                    part.get_content_charset(),
                    'replace'
                )
            except Exception:
                body += str(part.get_payload(decode=True))

        elif part.get_content_type() == "text/html":
            if html is None:
                html = ""
            html += str(
                part.get_payload(decode=True),
                part.get_content_charset(),
                'replace'
            )
    if html:
        html = html.strip()
    message = []
    if body:
        body = body.strip()
        # now lets parse the first part of the message that is not "quoted"
        blocks = 0
        for line in body.split('\n'):
            if line.startswith('>'):
                blocks += 1
                if blocks > 3:
                    break
                continue
            blocks = 0
            message.append(line.strip())
    message = "\n".join(message).strip()
    from_addr = parseaddr(msgobj.get('From'))
    date_time = parsedate_to_datetime(msgobj.get('Date'))
    return objict({
        'subject': subject.strip(),
        'body': body,
        'sent_at': date_time,
        'message': message,
        'html': html,
        'from_email': from_addr[1],
        'from_name': from_addr[0],
        'to': msgobj.get("To"),
        'to_addrs': getaddresses(msgobj.get_all("To", [])),
        'cc': msgobj.get("Cc"),
        'cc_addrs': getaddresses(msgobj.get_all("Cc", [])),
        'attachments': attachments,
    })


def parseAttachment(message_part):
    content_disposition = message_part.get("Content-Disposition", None)
    if content_disposition:
        dispositions = content_disposition.strip().split(";")
        if dispositions[0] in ["attachment", "inline"]:
            attachment = objict()
            attachment.payload = message_part.get_payload(decode=False)
            attachment.content_type = message_part.get_content_type()
            attachment.encoding = message_part.get("Content-Transfer-Encoding", "utf8")
            attachment.name = None
            attachment.create_date = None
            attachment.mod_date = None
            attachment.read_date = None
            # print dispositions
            for param in dispositions[1:]:
                name,value = param.split("=")
                name = name.strip().lower()
                if name == "filename":
                    attachment.name = value
                elif name in ["create-date", "creation-date"]:
                    attachment.create_date = value
                elif name == "modification-date":
                    attachment.mod_date = value
                elif name == "read-date":
                    attachment.read_date = value
            return attachment
    return None


def toFileObject(attachment):
    obj = StringIO(toString(attachment.payload))
    obj.name = attachment.name
    return obj


def toString(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value

