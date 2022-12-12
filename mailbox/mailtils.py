from io import StringIO
import email
from email.utils import parseaddr, parsedate, getaddresses
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
    date_time = parsedate(msgobj.get('Date'))
    return objict({
        'subject': subject.strip(),
        'body': body,
        'sent_at': date_time,
        'message': message,
        'html': html,
        'from_email': from_addr[1],
        'from_name': from_addr[0],
        'to': getaddresses(msgobj.get_all("To", [])),
        'cc': getaddresses(msgobj.get_all("Cc", [])),
        'attachments': attachments,
    })


def parseAttachment(message_part):
    content_disposition = message_part.get("Content-Disposition", None)
    if content_disposition:
        dispositions = content_disposition.strip().split(";")
        if bool(content_disposition and dispositions[0].lower() == "attachment"):
            file_data = message_part.get_payload(decode=True)
            # Used a StringIO object since PIL didn't seem to recognize
            # images using a custom file-like object
            attachment = StringIO(toString(file_data))
            attachment.content_type = message_part.get_content_type()
            attachment.size = len(file_data)
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
                    attachment.create_date = value  #TODO: datetime
                elif name == "modification-date":
                    attachment.mod_date = value #TODO: datetime
                elif name == "read-date":
                    attachment.read_date = value #TODO: datetime
            return attachment
    return None


def toString(value):
    if isinstance(value, bytes):
        value = value.decode()
    elif isinstance(value, bytearray):
        value = value.decode("utf-8")
    elif isinstance(value, (int, float)):
        value = str(value)
    return value

