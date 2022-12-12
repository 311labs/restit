from django.db import models
from rest import models as rm


class Mailbox(models.Model, rm.RestModel, rm.MetaDataModel):
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    modified = models.DateTimeField(auto_now=True)
    email = models.CharField(max_length=255, db_index=True)
    state = models.IntegerField(default=0, db_index=True)
    # define how this email address should be handeled 
    tq_app = models.CharField(max_length=255, null=True, default=None)
    tq_handler = models.CharField(max_length=255, null=True, default=None)
    tq_channel = models.CharField(max_length=255, null=True, default=None)


class MailboxMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(Mailbox, related_name="properties", on_delete=models.CASCADE)


class Message(models.Model, rm.RestModel):
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    modified = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField()

    state = models.IntegerField(default=0, db_index=True)

    to_email = models.CharField(max_length=255, db_index=True)
    to_name = models.CharField(max_length=255, null=True, default=None)
    to = models.TextField()
    cc = models.TextField()

    from_email = models.CharField(max_length=255, db_index=True)
    from_name = models.CharField(max_length=255, null=True, default=None)
    
    subject = models.CharField(max_length=255, null=True, default=None)
    message = models.TextField(null=True, default=None)

    body = models.TextField(null=True, default=None)
    html = models.TextField(null=True, default=None)


class Attachment(models.Model, rm.RestModel):
    created = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    name = models.CharField(max_length=255, null=True, default=None)
    message = models.ForeignKey(Message, related_name="attachments", on_delete=models.CASCADE)
    media = models.ForeignKey("medialib.MediaItem", related_name="attachments", on_delete=models.CASCADE)
