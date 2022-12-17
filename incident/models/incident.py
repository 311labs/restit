from django.db import models
from django.conf import settings

from rest import models as rm
from rest import helpers as rh
from taskqueue.models import Task


INCIDENT_STATE_NEW = 0
INCIDENT_STATE_OPENED = 1
INCIDENT_STATE_PAUSED = 2
INCIDENT_STATE_IGNORE = 3
INCIDENT_STATE_RESOLVED = 4

INCIDENT_STATES = [
    (INCIDENT_STATE_NEW, "new"),
    (INCIDENT_STATE_OPENED, "opened"),
    (INCIDENT_STATE_PAUSED, "paused"),
    (INCIDENT_STATE_IGNORE, "ignored"),
    (INCIDENT_STATE_RESOLVED, "resolved"),
]


class Incident(models.Model, rm.RestModel, rm.MetaDataModel):
    class RestMeta:
        POST_SAVE_FIELDS = ["level", "catagory"]
        SEARCH_FIELDS = ["description", "hostname"]
        # VIEW_PERMS = ["example_permission"]
        GRAPHS = {
            "default": {
                "extra": ["metadata"],
                "graphs": {
                    "group": "basic",
                    "assigned_to": "basic"
                },
            }
        }

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    description = models.CharField(max_length=200)

    group = models.ForeignKey("account.Group", on_delete=models.SET_NULL, null=True, default=None)
    assigned_to = models.ForeignKey("account.Member", on_delete=models.SET_NULL, null=True, default=None)
    
    priority = models.IntegerField(default=0)  # 1-10, 1 being the highest
    state = models.IntegerField(default=0, choices=INCIDENT_STATES)  # 0=new, 1=opened, 2=paused, 3=ignore, 4=resolved

    rule = models.ForeignKey("incident.Rule", on_delete=models.SET_NULL, null=True, default=None)

    def removeWatcher(self, wid):
        pass

    def on_rest_saved(self, request, is_new=False):
        if is_new:
            if self.rule:
                if self.rule.action in [None, "notify"]:
                    if self.group is not None:
                        # all member of the group are notified because it is an incident group
                        self.group.notifyMembers(
                            subject=F"New Incident - {self.description}",
                            template="incident/email/incident_change.html",
                            context=None,
                            email_only=True)
                elif self.rule.action.startswith("task:"):
                    fields = self.task.action.split(':')
                    Task.Publish(fields[1], fields[2], channel=fields[3])
            return

        self.logHistory(request=request)
        if request != None and len(request.FILES):
            for name, value in request.FILES.items():
                self.logHistory(kind="media", media=value, request=request)
        if request != None and "DATA" in request and "note" in request.DATA:
            self.logHistory(kind="note", note=request.DATA.get("note"), request=request)

    def logHistory(self, kind="history", note=None, media=None, request=None):
        if request is None:
            request = self.getActiveRequest()

        h = IncidentHistory(
            parent=self,
            to=self.assigned_to,
            note=note,
            kind=kind,
            priority=self.priority,
            state=self.state)
        if request is not None:
            h.by = request.member
        if media is not None:
            h.saveMediaFile(media, "media", media.name)
        h.save()
        self.notifyWatchers(subject=F"Incident:{self.id} Change - {self.description}", history=h)

    def notifyWatchers(self, subject, history=None):
        # this should notify all users in our incident group of the change
        if self.group is not None:
            # all member of the group are notified because it is an incident group
            self.group.notifyMembers(
                subject=subject,
                template="incident/email/incident_change.html",
                context=None,
                email_only=True)


class IncidentMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(Incident, related_name="properties", on_delete=models.CASCADE)


class IncidentHistory(models.Model, rm.RestModel):
    class Meta:
        ordering = ['-created']

    class RestMeta:
        SEARCH_FIELDS = ["to__username", "note"]
        GRAPHS = {
            "default": {
                "extra":[
                    ("get_state_display", "state_display"),
                    ("get_priority_display", "priority_display"),
                ],
                "graphs":{
                    "by":"basic",
                    "to":"basic",
                    "media": "basic"
                }
            },
        }
    parent = models.ForeignKey(Incident, related_name="history", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    group = models.ForeignKey("account.Group", blank=True, null=True, default=None, related_name="+", on_delete=models.CASCADE)

    kind = models.CharField(max_length=80, blank=True, null=True, default=None, db_index=True)

    to = models.ForeignKey("account.Member", blank=True, null=True, default=None, related_name="+", on_delete=models.CASCADE)
    by = models.ForeignKey("account.Member", blank=True, null=True, default=None, related_name="+", on_delete=models.CASCADE)

    state = models.IntegerField(default=0)
    priority = models.IntegerField(default=0)

    note = models.TextField(blank=True, null=True, default=None)
    media = models.ForeignKey("medialib.MediaItem", related_name="+", null=True, default=None, on_delete=models.CASCADE)

