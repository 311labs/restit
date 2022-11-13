#!/usr/bin/python
import os, sys
from io import StringIO
from django.conf import settings
import imaplib
import email
from email.parser import Parser as EmailParser
from email.utils import parseaddr, parsedate
from email.header import decode_header
import time
from datetime import datetime
import tempfile
from rest.helpers import toString
from rest.uberdict import UberDict
from optparse import OptionParser

# lazy log
def log(msg):
    # print "{0}\t{1}".format(datetime.now(), msg)
    # sys.stdout.flush()
    pass

import base64
import xmltodict

class NotSupportedMailFormat(Exception):
    pass

def parse_attachment(message_part):
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

def parse_raw_message(msgobj):
    """
    Parse the email and return a dictionary of relevant data.
    """
    if type(msgobj) in [str, str]:
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
        attachment = parse_attachment(part)
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
    to_addr = parseaddr(msgobj.get('To'))
    date_time = parsedate(msgobj.get('Date'))
    return UberDict({
        'subject' : subject.strip(),
        'body' : body,
        'date_time' : date_time,
        'message': message,
        'html' : html,
        'from_email': from_addr[1],
        'from' : from_addr[1], # Leave off the name and only return the address
        'from_name' : from_addr[0], # Leave off the name and only return the address
        'to_email': to_addr[1],
        'to' : to_addr[1], # Leave off the name and only return the address
        'to_name' : to_addr[0], # Leave off the name and only return the address
        'attachments': attachments,
    })

class MailManHandler(object):
    def saveAttachment(self, attr, lib=None, owner=None, group=None):
        if lib is None:
            lib = MediaLibrary(name="email", owner=owner, group=group)
            lib.save()
        upload_kind = validate_upload(attr)
        media = MediaItem(library=lib, name=attr.name, owner=owner, kind=upload_kind, newfile=attr)
        media.save()
        return media

    def on_message(self, muid, msg):
        pass


class MailMan(object):
    def __init__(self, host, username, password, timeout=60, markseen=False):
        self.handlers = []
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self.markseen = markseen
        self.con = None
        self.messages = []
        
    def connect(self):
        log("creating connection")
        self.con = imaplib.IMAP4_SSL(self.host)
        log("logging in")
        self.con.login(self.username, self.password)

    def disconnect(self):
        self.con.logout()

    def addHandler(self, handler):
        self.handlers.append(handler)

    def searchMail(self, unseen_only=True, search_from=None, search_subject=None, max_messages=25):
        """
        search mail and return list of mail uids
        """
        if not self.con:
            self.connect()
        self.con.select(readonly=True)
        search = "ALL"
        if unseen_only:
            search = "UNSEEN"
        search = [search]
        if search_subject:
            search.append('SUBJECT "{0}"'.format(search_subject))
        if search_from:
            search.append('FROM "{0}"'.format(search_from))
        search = "({0})".format(' '.join(search))
        result, uids = self.con.uid('search', None, search) # search and return uids instead
        uids = uids[0].split()
        log("{0}".format(uids))
        if len(uids) > max_messages:
            uids = uids[:max_messages]
        return uids

    def checkMail(self, unseen_only=True, search_from=None, search_subject=None, max_messages=25):
        self.messages = []
        if not self.con:
            self.connect()
        self.con.select(readonly=True)
        log("checking inbox for unread mail")
        #search = "ALL"
        # search = "SINCE {0} UNSEEN".format(datetime.now().strftime("%d-%m-%Y"))
        search = "ALL"
        if unseen_only:
            search = "UNSEEN"
        search = [search]
        if search_subject:
            search.append('SUBJECT "{0}"'.format(search_subject))
        if search_from:
            search.append('FROM "{0}"'.format(search_from))
        search = "({0})".format(' '.join(search))
        result, uids = self.con.uid('search', None, search) # search and return uids instead
        uids = uids[0].split()
        log("{0}".format(uids))
        if len(uids) > max_messages:
            uids = uids[:max_messages]
        for uid in uids:
            self.messages.append(self.fetchMessage(uid))
        log("check complete")
        messages = self.messages
        self.messages = []
        return messages

    def pushToHandlers(self, muid, msg):
        handled = False
        msg.id = muid
        for handler in self.handlers:
            if handler.on_message(muid, msg):
                handled = True
        if handled or self.markseen:
            self.markSeen(muid)

    def fetchMessage(self, muid):
        log("fetch message({0})".format(muid))
        self.con.select(readonly=True)
        results, data = self.con.uid('fetch', muid, "(RFC822)")
        if results != "OK":
            log("ERROR: fetchMessage({0}) failed with response({1})".format(muid, results))
            return False
        log("message fetched")
        msg = parse_raw_message(email.message_from_string(toString(data[0][1])))
        self.pushToHandlers(muid, msg)
        return msg

    def markSeen(self, muid):
        self.con.select(readonly=False)
        log("- marking '{0}' as seen".format(muid))
        typ, data = self.con.uid("STORE", muid,'+FLAGS','\Seen')
        log("- output '{0}' - '{1}'".format(typ, data))

    def markUnseen(self, muid):
        self.con.select(readonly=False)
        log("- marking '{0}' as unseen".format(muid))
        typ, data = self.con.uid("STORE", muid,'-FLAGS','\Seen')
        log("- output '{0}' - '{1}'".format(typ, data))

    def done(self):
        log("done")
        self.con.send("DONE\r\n")
        self.con.loop = False
        self.con.readline() #otherwise imaplib.idle() freaks out
