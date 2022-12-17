from django.db import models

from rest import models as rm
from rest import log
from rest import settings
import metrics

from datetime import datetime, timedelta
from .incident import Incident
from .rules import Rule

INCIDENT_METRICS = settings.get("INCIDENT_METRICS", False)
INCIDENT_EVENT_METRICS = settings.get("INCIDENT_EVENT_METRICS", False)


logger = log.getLogger("incident", filename="incident.log")

"""
very generic 
external system can post an event
{
     "description": "Critical Test Event",
     "hostname": "r1",
     "details": "A critical event occurred on r1 running blah blah",
     "level": 7,
     "category": "prepaid.event",
     "metadata": {
        "error_stack": "....."
     }
}
"""


class Event(models.Model, rm.RestModel, rm.MetaDataModel):
    class RestMeta:
        POST_SAVE_FIELDS = ["level", "catagory"]
        SEARCH_FIELDS = ["description", "hostname"]
        # VIEW_PERMS = ["example_permission"]
        GRAPHS = {
            "default": {
                "extra": ["metadata"],
                "graphs": {
                    "group": "basic",
                    "created_by": "basic"
                },
            },
            "detailed": {
                "extra": ["metadata"],
                "graphs": {
                    "group": "basic",
                    "created_by": "basic",
                    "generic__component": "basic",
                },
            },
        }

    created = models.DateTimeField(auto_now_add=True)
    reporter_ip = models.CharField(max_length=16, blank=True, null=True, default=None, db_index=True)

    hostname = models.CharField(max_length=255, blank=True, null=True, default=None, db_index=True)
    description = models.CharField(max_length=84)
    details = models.TextField(default=None, null=True)

    level = models.IntegerField(default=0, db_index=True)
    category = models.CharField(max_length=124, db_index=True)
    
    component = models.SlugField(max_length=250, null=True, blank=True, default=None)
    component_id = models.IntegerField(null=True, blank=True, default=None)

    # this allows us to bundle multiple events to an incident
    incident = models.ForeignKey(
        Incident, null=True, default=None, 
        related_name="events", on_delete=models.SET_NULL)

    def runRules(self):
        for rule in Rule.objects.filter(category=self.category).order_by("priority"):
            if rule.run(self):
                return rule
        return None

    def on_rest_saved(self, request, is_new=False):
        if INCIDENT_EVENT_METRICS:
            if self.hostname:
                metrics.metric(f"incident_evt_{self.hostname}", category="incident_events", min_granularity="hourly")
            metrics.metric("incident_evt", category="incident_events", min_granularity="hourly")

        self.setProperty("level", self.level)
        if request is not None:
            self.reporter_ip = request.ip
        # run through rules for the category
        hit_rule = self.runRules()
        priority = 10
        incident = None
        if hit_rule is not None:
            priority = hit_rule.priority
            if hit_rule.bundle > 0:
                # calculate our bundle start time
                when = datetime.now() - timedelta(minutes=hit_rule.bundle)
                incident = Incident.objects.filter(rule=hit_rule, created__gte=when, component=self.hostname).last()
            elif hit_rule.action == "ignore":
                # we do not create an incident, we just move on
                self.save()
                return
        elif self.level > 3:
            # we ignore levels 4 and higher if they did not create a rule
            self.save()
            logger.info(f"ignore event {self.pk} {self.description}")
            return

        # always create an incident 
        is_incident_new = False
        if incident is None:
            is_incident_new = True
            incident = Incident(rule=hit_rule, priority=priority, component=self.hostname)
            if hit_rule is not None:
                incident.group = hit_rule.group
            # TODO possibly make this smarter?
            incident.description = self.description
            incident.save()
        self.incident = incident
        self.save()
        if INCIDENT_METRICS:
            if self.hostname:
                metrics.metric(f"incidents_{self.hostname}", category="incidents", min_granularity="hourly")
            metrics.metric("incidents", category="incidents", min_granularity="hourly")
        # fire this off so incident notifies
        if is_incident_new:
            incident.on_rest_saved(request, is_new=is_incident_new)
        

class EventMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(Event, related_name="properties", on_delete=models.CASCADE)

