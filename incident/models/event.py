from django.db import models

from rest import models as rm

from datetime import datetime, timedelta
from .incident import Incident
from .rules import Rule

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

    def set_level(self, value):
        self.level = value
        self.setProperty("level", value)

    def set_category(self, value):
        self.catagory = value
        self.setProperty("category", value)

    def on_rest_saved(self, request, is_new=False):
        rules = Rule.objects.filter(category=self.category).order_by("priority")
        hit_rule = None
        priority = 10
        for rule in rules:
            if rule.run(self):
                hit_rule = rule
                priority = rule.priority
                break

        if hit_rule is not None:
            # create incident
            incident = None
            if hit_rule.bundle > 0:
                # calculate our bundle start time
                when = datetime.now() - timedelta(minutes=hit_rule.bundle)
                incident = Incident.objects.filter(rule=hit_rule, created__gte=when).last()
        # always create an incident 
        is_incident_new = False
        if incident is None:
            is_incident_new = True
            incident = Incident(rule=hit_rule, priority=priority)
            if hit_rule is not None:
                incident.group = hit_rule.group
            # TODO possibly make this smarter?
            incident.description = self.description
            incident.save()
        self.incident = incident
        if request is not None:
            self.reporter_ip = request.ip
        self.save()
        # fire this off so incident notifies
        incident.on_rest_saved(request, is_new=is_incident_new)
        

class EventMetaData(rm.MetaDataBase):
    parent = models.ForeignKey(Event, related_name="properties", on_delete=models.CASCADE)

