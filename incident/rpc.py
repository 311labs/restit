from rest import decorators as rd
from rest import views as rv
from rest import helpers as rh
from . import models as am
from .parsers import ossec


@rd.urlPOST(r'^ossec/alert$')
def ossec_alert_creat_from_request(request):
    payload = request.DATA.get("payload")
    if payload:
        try:
            # TODO make this a task (background it)
            od = ossec.parseAlert(request, payload)
            # lets now create a local event
            if od is not None:
                level = 10
                if od.level > 10:
                    level = 1
                elif od.level > 7:
                    level = 2
                elif od.level == 6:
                    level = 3
                elif od.level == 5:
                    level = 4
                elif od.level == 4:
                    level = 6
                elif od.level <= 3:
                    level = 8
                am.Event.createFromDict(None, {
                    "hostname": od.hostname,
                    "description": od.title,
                    "level": level,
                    "metadata": od.toDict(graph="default")
                })
        except Exception:
            rh.log_exception("during ossec alert", payload)
    return rv.restStatus(request, False, error="no alert data")


@rd.urlGET(r'^ossec$')
@rd.urlGET(r'^ossec/(?P<pk>\d+)$')
@rd.login_required
def on_ossec(request, pk=None):
    return am.ServerOssecAlert.on_rest_request(request, pk)


@rd.urlPOST(r'^event$')
def rest_on_create_event(request, pk=None):
    # TODO check for key?
    resp = am.Event.on_rest_request(request)
    return rv.restStatus(request, True)


@rd.urlGET(r'^event$')
@rd.urlGET(r'^event/(?P<pk>\d+)$')
@rd.login_required
def rest_on_event(request, pk=None):
    return am.Event.on_rest_request(request, pk)


@rd.url(r'^incident$')
@rd.url(r'^incident/(?P<pk>\d+)$')
@rd.login_required
def rest_on_incident(request, pk=None):
    return am.Incident.on_rest_request(request, pk)


@rd.url(r'^incident/history$')
@rd.url(r'^incident/history/(?P<pk>\d+)$')
@rd.login_required
def rest_on_incident_history(request, pk=None):
    return am.IncidentHistory.on_rest_request(request, pk)


@rd.url(r'^rule$')
@rd.url(r'^rule/(?P<pk>\d+)$')
@rd.login_required
def rest_on_rule(request, pk=None):
    return am.Rule.on_rest_request(request, pk)


@rd.url(r'^rule/check$')
@rd.url(r'^rule/check/(?P<pk>\d+)$')
@rd.login_required
def rest_on_rule_check(request, pk=None):
    return am.RuleCheck.on_rest_request(request, pk)

