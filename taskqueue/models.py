from django.db import models
from rest import settings

from rest.models import RestModel, MetaDataModel, MetaDataBase
from rest.fields import JSONField
from rest.uberdict import UberDict
from rest import RemoteEvents
from account.models import Member
import importlib

import traceback

import time
from datetime import datetime, timedelta
NOT_FOUND = "-NOT-FOUNT-"

TASK_STATE_SCHEDULED = 0
TASK_STATE_STARTED = 1
TASK_STATE_RETRY = 2
TASK_STATE_COMPLETED = 10
TASK_STATE_FAILED = -1
TASK_STATE_CANCELED = -2

TASK_STATES = [
    (TASK_STATE_SCHEDULED, 'scheduled'),
    (TASK_STATE_STARTED, 'started'),
    (TASK_STATE_RETRY, 'retry_later'),
    (TASK_STATE_COMPLETED, 'completed'),
    (TASK_STATE_FAILED, 'failed'),
    (TASK_STATE_CANCELED, 'canceled')
]

def getAppHandler(app_name, fname):
    try:
        # module = __import__(app_name + '.tq', globals(), locals(), ['*'], 0)
        module = importlib.import_module(app_name + '.tq')

    except ImportError as err:
        return None

    if hasattr(getattr(module, fname, None), '__call__'):
        return getattr(module, fname)
    return None

class Task(models.Model, RestModel):
    """
    This is the state of a remote task.  This model is a backup store to a task that was scheduled
    via Task.Publish(data)
    TQ_SUBSCRIBE = ["tq_web_request", "tq_model_handler", "tq_app_handler"]

    tq_model_handler is a method on a django Model
    tq_app_handler is a method in a modules tq module... example (mymodule.tq.on_tq_test)

    Extends:
        models.Model
        RestModel
    """
    class RestMeta:
        DEFAULT_SORT = "-modified"
        POST_SAVE_FIELDS = ["action"]
        SEARCH_FIELDS = ["channel", "model", "fname", "data"]
        SEARCH_TERMS = [
            "channel", "model", "fname",
            "data", "reason", "runtime", "state"
        ]
        GRAPHS = {
            "list": {
                "fields":[
                    'id',
                    'created',
                    'modified',
                    'started_at',
                    'completed_at',
                    'stale_after',
                    'cancel_requested',
                    'state',
                    'runtime',
                    'channel',
                    'model',
                    'fname',
                    ('truncate_data', 'data'),
                    'reason',
                    '_started',
                ],
                "extra": [("get_state_display", "state_display")],
            },
            "default": {
                "extra": [("get_state_display", "state_display")],
            },
            "detailed": {
                "extra": [("get_state_display", "state_display")],
            },
        }
    created = models.DateTimeField(db_index=True, auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(default=None, null=True, blank=True)
    completed_at = models.DateTimeField(default=None, null=True, blank=True)
    stale_after = models.DateTimeField(default=None, null=True, blank=True)
    scheduled_for = models.DateTimeField(default=None, null=True, blank=True, db_index=True)
    cancel_requested = models.BooleanField(default=False, blank=True)
    state = models.IntegerField(db_index=True, default=TASK_STATE_SCHEDULED, choices=TASK_STATES)
    runtime = models.IntegerField(default=0)
    attempts = models.IntegerField(default=0)
    channel = models.CharField(max_length=200, db_index=True, default="tq_task")
    model = models.CharField(max_length=200, db_index=True)
    fname = models.CharField(max_length=200, default=None, null=True, blank=True)
    data = JSONField(default=None, null=True, blank=True)
    reason = models.CharField(max_length=255, default=None, null=True, blank=True)
    _started = 0

    @property
    def is_stale(self):
        if not self.stale_after:
            return False
        return self.stale_after >= datetime.now()

    @property
    def truncate_data(self):
        if self.data and self.data.data:
            temp = self.data
            temp.data = "...truncated..."
            return temp
        return self.data

    @property
    def created_age(self):
        return (datetime.now() - self.created).total_seconds()

    @property
    def modified_age(self):
        return (datetime.now() - self.modified).total_seconds()

    @property
    def current_runtime(self):
        if self.state in [10, -1]:
            return self.runtime
        if not self.started_at:
            return self.runtime
        return (datetime.now() - self.started_at).total_seconds()

    def set_action(self, value):
        if value == "retry_now":
            self.retry_now()
        elif value == "cancel":
            request = self.getActiveRequest()
            self.reason = "cancel request by {}".format(request.member.username)
            self.cancel(request.DATA.get("reason", "canceled by {}".format(request.member.username)))

    # def auditlog(self, action, message, request=None, path=None, component="taskqueue.Task"):
    #     # message, level=0, request=None, component=None, pkey=None, action=None, group=None, path=None, method=None
    #     # PersistentLog.log(message=message, level=1, action=action, request=request, component=component, pkey=self.pk, path=path, method=self.fname)
    #     raise Exception("auditlog called but is not supported")

    def log(self, text, kind="info"):
        TaskLog.Log(self, text, kind=kind)

    def log_exception(self, text, kind="exception"):
        self.log(str(text), kind=kind)
        self.log(traceback.format_exc(), "exception")

    def started(self):
        self.state = TASK_STATE_STARTED
        self.started_at = datetime.now()
        self._started = time.time()
        self.attempts += 1
        self.save()

    def retry_later(self, reason=None, from_now_secs=None):
        if reason:
            self.reason = reason
        if from_now_secs:
            # this will not run the task again until after this time has been hit
            self.scheduled_for = datetime.now() + timedelta(seconds=from_now_secs)
        self.state = TASK_STATE_RETRY
        self.cancel_requested = False
        self.save()

    def retry_now(self):
        self.state = TASK_STATE_SCHEDULED
        self.cancel_requested = False
        self.save()
        self.publish()

    def completed(self):
        self.completed_at = datetime.now()
        self.runtime = int(time.time() - self._started)
        self.state = TASK_STATE_COMPLETED
        self.save()

    def failed(self, reason=None):
        if reason and len(reason) > 250:
            reason = reason[:250]
        self.reason = reason
        self.state = TASK_STATE_FAILED
        self.notifyError()
        self.save()

    def notifyError(self, kind="Failure"):
        subject = "TaskQueue - {}".format(kind)
        handler = "unknown bg_handler"
        if self.data:
            handler = self.data.get("bg_handler")
        msg = "{}:{}<br>\n{}".format(self.model, handler, self.reason)
        # sms_msg = "{}\n{}".format(subject, msg)
        # Member.notifyWithPermission("taskqueue_alerts", subject, msg, sms_msg=sms_msg)
        metadata = {
            "server": settings.get("HOSTNAME", "unknown"),
            "task": self.pk,
            "reason": self.reason,
            "kind": kind,
            "app": self.model,
            "fname": self.fname,
            "channel": self.channel,
            "handler": handler
        }
        try:
            import incident
            incident.event_now(
                "taskqueue_errors", description=subject, details=msg, 
                level=3, metadata=metadata)
        except Exception as err:
            self.log(str(err), kind="error")

    def cancel(self, reason=None):
        self.cancel_requested = True
        self.save()
        out = UberDict()
        out.reason = reason
        out.pk = self.pk
        return RemoteEvents.publish("tq_cancel", out)

    def publish(self, channel=None):
        out = UberDict()
        out.pk = self.pk
        out.model = self.model
        out.fname = self.fname
        out.data = self.data
        if not channel:
            channel = self.channel
        return RemoteEvents.publish(channel, out)

    def getHandler(self):
        if self.channel.startswith("tq_app_handler"):
            return getAppHandler(self.model, self.fname)
        app, mname = self.model.split('.')
        model = self.restGetModel(app, mname)
        if not model:
            return None
        return getattr(model, self.fname, None)

    @classmethod
    def WebRequest(cls, url, data, fname="POST", stale_after_seconds=0):
        tdata = UberDict()
        tdata.url = url
        tdata.data = data
        task = cls(channel="tq_hook",model="tq_web_request", fname=fname, data=tdata)
        if stale_after_seconds:
            task.stale_after = datetime.now() + timedelta(seconds=stale_after_seconds)
        task.save()
        task.publish()
        return task

    @classmethod
    def EmailRequest(cls, address, data, filename=None, subject=None):
        tdata = UberDict()
        tdata.address = address
        tdata.filename = filename
        tdata.subject = subject
        tdata.data = data
        task = cls(channel="tq_hook",model="tq_email_request", data=tdata)
        task.save()
        task.publish()
        return task

    @classmethod
    def SMSRequest(cls, phone, data):
        tdata = UberDict()
        tdata.phone = phone
        tdata.data = data
        task = cls(channel="tq_hook",model="tq_sms_request", data=tdata)
        task.save()
        task.publish()
        return task

    @classmethod
    def SFTPRequest(cls, host, data, filename, username, password):
        tdata = UberDict()
        tdata.host = host
        tdata.filename = filename
        # TODO this should be more secure!
        # TODO support ssh keys?
        tdata.username = username
        tdata.password = password
        tdata.data = data
        task = cls(channel="tq_hook",model="tq_sftp_request", data=tdata)
        task.save()
        task.publish()
        return task
    
    @classmethod
    def S3Request(cls, bucket, data, folder, aws, secret, filename, when):
        tdata = UberDict()
        tdata.bucket = bucket
        tdata.filename = filename
        tdata.data = data
        tdata.folder = folder
        tdata.aws = aws
        tdata.secret = secret
        tdata.when = str(when)
        task = cls(channel="tq_hook",model="tq_s3_request", data=tdata)
        task.save()
        task.publish()
        return task

    @classmethod
    def PublishModelTask(cls, model_name, fname, data, stale_after_seconds=0, channel="tq_model_handler", scheduled_for=scheduled_for):
        return cls.Publish(cls, model_name, fname, data, stale_after_seconds, channel, scheduled_for)

    @classmethod
    def Publish(cls, app_name, fname, data=None, stale_after_seconds=0, channel="tq_app_handler", scheduled_for=None):
        # tq_handler will check for a function in the django app tq.py
        task = cls(model=app_name, fname=fname, data=data, channel=channel, scheduled_for=scheduled_for)
        if stale_after_seconds:
            task.stale_after = datetime.now() + timedelta(seconds=stale_after_seconds)
        if scheduled_for is not None:
            # this means we just save as a retry, and let it be scheduled for later
            task.state = TASK_STATE_RETRY
            task.save()
            return task
        task.save()
        task.publish(channel)
        return task

    @classmethod
    def FromEvent(cls, event):
        if not event.data or not event.data.pk:
            return None
        return cls.objects.filter(pk=event.data.pk).last()

    @classmethod
    def PublishTest(cls, count=1, sleep_time=20.0):
        for i in range(1, count+1):
            cls.Publish("taskqueue", "on_tq_test", {"published_at": time.time(), "index":i, "sleep_time": sleep_time})

    @classmethod
    def RestartEngine(cls):
        RemoteEvents.publish("tq_restart", {})

class TaskLog(models.Model, RestModel):
    created = models.DateTimeField(db_index=True, auto_now_add=True)
    task = models.ForeignKey(Task, related_name="logs", on_delete=models.CASCADE)
    kind = models.CharField(max_length=64, default=None, null=True, blank=True)
    text = models.TextField()

    @classmethod
    def Log(cls, task, text, kind="info"):
        log = cls(task=task, text=text, kind=kind)
        log.save()
        return log


class TaskHook(models.Model, RestModel, MetaDataModel):
    """
    This does nothing on its own.  It simply allows for the defining of task hooks
    that can be used during execution of ones own task logic.  The task logic would
    look up the group and channel (just a unique identifier for when the hook is caught)

    use properties to add extra metadata for this hook.
        - group     group this hook belongs to
        - kind      HTTP_POST, EMAIL, SMS, SFTP
        - data_format    file format, csv, json, pdf
        - endpoint  web address, email, sms or other
        - channel   a unique keyword to use to search when looking for the hook
        - model     django app.Model string to use to search when looking for
    """
    class RestMeta:
        CAN_DELETE = True
        DEFAULT_SORT = "-modified"
        SEARCH_FIELDS = ["channel", "model", "endpoint"]
        SEARCH_TERMS = [
            "channel", "model", "fname",
            "data", "reason", "runtime", "state"
        ]
        GRAPHS = {
            "list": {
                "extra":["metadata"],
                "graphs": {
                    "group":"basic"
                }
            },
            "default": {
                "extra":["metadata"],
                "graphs": {
                    "group":"basic"
                }
            },
            "detailed": {
                "graphs": {
                    "self":"default"
                }
            },
        }

    created = models.DateTimeField(db_index=True, auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    group = models.ForeignKey("account.Group", blank=True, null=True, default=None, related_name="+", on_delete=models.CASCADE)
    kind = models.CharField(max_length=200, blank=True, null=True)
    data_format = models.CharField(max_length=32, default="json")
    endpoint = models.CharField(max_length=200, blank=True, null=True)
    state = models.IntegerField(default=1, choices=[(0, 'inactive'), (1, 'active')], db_index=True)

    # channel is just a unique keyword to check for hooks
    channel = models.CharField(max_length=200, db_index=True, default="tq_hook")
    # if this only gets fired for a particular model
    model = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    def trigger(self, data, when=None):
        task = None
        if self.kind == "HTTP_POST":
            # url, data, fname="POST", stale_after_seconds=0
            task = Task.WebRequest(self.endpoint, data)
        elif self.kind == "HTTP_GET":
            task = Task.WebRequest(self.endpoint, data, fname='GET')
        elif self.kind == "EMAIL":
            task = Task.EmailRequest(
                self.endpoint, data,
                self.getProperty("filename", "{date.month:02d}{date.day:02d}{date.year}." + self.data_format),
                self.getProperty("subject", "{date.month:02d}{date.day:02d}{date.year}"))
        elif self.kind == "SFTP":
            task = Task.SFTPRequest(
                self.endpoint, data,
                self.getProperty("filename", "{date.month:02d}{date.day:02d}{date.year}." + self.data_format),
                self.getProperty("username"),
                self.getProperty("password"))
        elif self.kind == "SMS":
            task = Task.SMSRequest(self.endpoint, data)
        elif self.kind == "S3":
            task = Task.S3Request(
                self.getProperty("bucket"), data,
                self.getProperty("folder", None),
                self.getProperty("aws", None),
                self.getProperty("secret", None),
                self.getProperty("filename", "{date.month:02d}{date.day:02d}{date.year}." + self.data_format),
                when)
        else:
            print("unknown hook kind: {}".format(self.kind))
        return task

class TaskHookMetaData(MetaDataBase):
    parent = models.ForeignKey(TaskHook, related_name="properties", on_delete=models.CASCADE)



