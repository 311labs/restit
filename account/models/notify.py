from django.db import models
from django.conf import settings

from rest.models import RestModel
from rest import mail as rest_mail

from .member import Member

from datetime import datetime, timedelta


class NotificationRecord(models.Model, RestModel):
    class RestMeta:
        CAN_SAVE = CAN_CREATE = False
        DEFAULT_SORT = "-created"
        SEARCH_FIELDS = ["subject"]
        SEARCH_TERMS = ["subject", ("to", "to__to_addr"), "body", "reason", "state", ("from", "from_addr")]
        GRAPHS = {
            "list": {
                "fields": ["id", ("get_state_display", "state_display"), "created", "subject", "from_addr", "to_emails", "reason", "state", "attempts"],
            },
            "default": {
                "extra": ["to_emails", ("get_state_display", "state_display")]
            }
        }
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    modified = models.DateTimeField(auto_now=True, editable=False)
    method = models.CharField(max_length=128, default="email", db_index=True)

    from_addr = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    reason = models.TextField()
    # new=0, queued=-5, sent=1
    state = models.IntegerField(default=0, choices=[(0, "new"), (-5, "queued"), (1, "sent"), (-10, "failed")], db_index=True)
    attempts = models.IntegerField(default=0)

    @property
    def to_emails(self):
        return list(self.to.all().values_list("to_addr", flat=True))

    def send(self, member_records=None):
        email_to = []
        save_records = True
        if not member_records:
            member_records = self.to.all()
            save_records = False
        for r in member_records:
            email_to.append(r.to_addr)
            if save_records:
                r.notification = self
                r.save()
        if NotificationRecord.canSend():
            try:
                rest_mail.send(
                    email_to,
                    self.subject,
                    self.body,
                    attachments=self.attachments.all(),
                    do_async=True
                )
                # self.reason = "sent"
                self.state = 1
            except Exception as err:
                self.reason = str(err)
                self.attempts += 1
                if self.attempts >= 3:
                    self.state = -10
                else:
                    self.state = -5
            self.save()
            return True
        if self.state != -5:
            self.state = -5
            self.save()
        return False

    def attach(self, name, mimetype, data):
        atmnt = NotificationAttachment(notification=self, name=name, mimetype=mimetype, data=data)
        atmnt.save()
        return atmnt

    def addAttachments(self, attachments):
        if not attachments:
            return False
        for a in attachments:
            if type(a) in [str, str]:
                # TODO handle file inport
                pass
            else:
                self.attach(a.name, a.mimetype, a.data)

    @classmethod
    def canSend(cls):
        max_emails_per_minute = getattr(settings, "MAX_EMAILS_PER_MINUTE", 30)
        last_email = NotificationRecord.objects.filter(state=1).last()
        now = datetime.now()
        if last_email and (now - last_email.created).total_seconds() < 30:
            # we sent an email less then a minute ago
            # now we can to count the number of message sent in last minute
            when = now - timedelta(seconds=60)
            sent = NotificationRecord.objects.filter(state=1, created__gte=when).count()
            return sent < max_emails_per_minute
        return True

    @classmethod
    def notifyFromEmails(cls, emails, subject, message=None, template=None, context=None, email_only=False, sms_msg=None, force=False, from_email=settings.DEFAULT_FROM_EMAIL, attachments=[]):
        Member = RestModel.getModel("account", "Member")
        members = Member.objects.filter(email__in=emails)
        cls.notify(members, subject, message, template, context, email_only, sms_msg, force, from_email, attachments)

    @classmethod
    def notify(cls, notify_users, subject, message=None, template=None, context=None, email_only=False, sms_msg=None, force=False, from_email=settings.DEFAULT_FROM_EMAIL, attachments=[]):
        # this will create a record for each email address message is sent to
        from telephony.models import SMS
        email_to = []
        email_list = []
        sms_to = []

        if not message and not template and subject:
            message = subject

        if not sms_msg and subject:
            sms_msg = subject
        if not sms_msg and message:
            sms_msg = message

        if subject and len(subject) > 80:
            epos = subject.find('. ') + 1
            if epos > 10:
                subject = subject[:epos]
            else:
                subject = subject[:80]
                subject = subject[:subject.rfind(' ')] + "..."

        if template:
            # render message now so we can save message
            message = rest_mail.renderBody(message, template, context)
            template = None
            context = None

        email_record = None
        for member in notify_users:
            via = member.getProperty("notify_via", "all")
            phone = member.getProperty("phone")
            email = member.email
            valid_email = email != None and "@" in email and "invalid" not in email
            allow_sms = not email_only and phone and (force or via in ["all", "sms"])
            allow_email = valid_email and (force or via in ["all", "email"])
            if not allow_email and not allow_sms:
                continue
            if allow_email and email not in email_list:
                email_list.append(email)
                nr = NotificationMemberRecord(member=member, to_addr=email)
                email_to.append(nr)
            if not email_only and allow_sms and phone not in sms_to:
                sms_to.append(phone)

        if sms_to:
            for phone in sms_to:
                SMS.send(phone, sms_msg)

        if email_to:
            # lets verify the db is working
            email_record = NotificationRecord(
                method="email",
                subject=subject,
                from_addr=from_email,
                body=message)
            try:
                email_record.save()
                email_record.addAttachments(attachments)
                email_record.send(email_to)
            except Exception as err:
                print(("failed to create record: {}".format(str(err))))
                # we need to send emails the old way
                addrs = []
                for to in email_to:
                    addrs.append(to.to_addr)
                rest_mail.send(
                    addrs,
                    subject,
                    message,
                    attachments=attachments,
                    do_async=True)


class NotificationAttachment(models.Model, RestModel):
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    notification = models.ForeignKey(NotificationRecord, related_name="attachments", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    mimetype = models.CharField(max_length=255)
    data = models.TextField()


class NotificationMemberRecord(models.Model, RestModel):
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    member = models.ForeignKey("account.Member", related_name="notifications", on_delete=models.CASCADE)
    notification = models.ForeignKey(NotificationRecord, related_name="to", on_delete=models.CASCADE)
    to_addr = models.CharField(max_length=255, db_index=True)


class BounceHistory(models.Model, RestModel):
    class RestMeta:
        CAN_SAVE = False
        SEARCH_FIELDS = ["address"]
        SEARCH_TERMS = [("email", "address"), ("to", "address"), "source", "reason", "state", ("user", "user__username")]
        GRAPHS = {
            "default": {
                "graphs": {
                    "user": "basic"
                }
            },
            "list": {
                "graphs": {
                    "user": "basic"
                }
            }
        }
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    user = models.ForeignKey("account.Member", related_name="bounces", null=True, blank=True, default=None, on_delete=models.CASCADE)
    address = models.CharField(max_length=255, db_index=True)
    kind = models.CharField(max_length=32, db_index=True)
    reason = models.TextField(null=True, blank=True, default=None)
    reporter = models.CharField(max_length=255, null=True, blank=True, default=None)
    code = models.CharField(max_length=32, null=True, blank=True, default=None)
    source = models.CharField(max_length=255, null=True, blank=True, default=None)
    source_ip = models.CharField(max_length=64, null=True, blank=True, default=None)

    @staticmethod
    def log(kind, address, reason, reporter=None, code=None, source=None, source_ip=None, user=None):
        obj = BounceHistory(kind=kind, address=address)
        obj.reason = reason
        obj.reporter = reporter
        obj.code = code
        obj.source = source
        obj.source_ip = source_ip
        if user is None:
            Member = RestModel.getModel("account", "Member")
            user = Member.objects.filter(email=address).last()
            # now lets check our bounced count, if more then 3, we turn off email
            if user:
                user.log("bounced", "{} bounced to {} from {}".format(kind, address, source_ip), method=kind)
                since = datetime.now() - timedelta(days=14)
                bounce_count = BounceHistory.objects.filter(user=user, created__gte=since).count()
                if bounce_count > 2:
                    # TODO notify support an account has been disabled because of bounce
                    user.setProperty("notify_via", "off")
                    user.log("disabled", "notifications disabled because email bounced", method="notify")
        else:
            # TODO notify support of unknown bounce
            pass
        obj.user = user
        obj.save()

