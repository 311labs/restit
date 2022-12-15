from rest import views as rv
from rest import decorators as rd
from rest import search
from rest import helpers as rest_helpers
from rest.uberdict import UberDict
from datetime import datetime, timedelta
from taskqueue import models as tq 

from django.db.models import Sum, Max, Count, Q
from django.db.models.functions import Trunc


@rd.url(r'^task$')
@rd.url(r'^task/(?P<pk>\d+)$')
@rd.login_required
def rest_on_task(request, pk=None):
    return tq.Task.on_rest_request(request, pk)


@rd.url(r'^task/log$')
@rd.url(r'^task/log/(?P<pk>\d+)$')
@rd.login_required
def rest_on_tasklog(request, pk=None):
    return tq.TaskLog.on_rest_request(request, pk)


@rd.url(r'^task/schedule$')
@rd.url(r'^task/schedule/(?P<pk>\d+)$')
@rd.login_required
def rest_on_tasklog(request, pk=None):
    return tq.ScheduledTask.on_rest_request(request, pk)


@rd.urlPOST(r'^task/publish$')
@rd.perm_required("manage_staff")
def rest_on_task_publish(request, pk=None):
    app = request.DATA.get("app").strip()
    module = request.DATA.get("module").strip()
    task_data = request.DATA.get("task_data").strip()
    if not app or not module:
        return rv.restStatus(request, False, error="Both app and module are required.")
    task = tq.Task.Publish(app, module, task_data)
    return rv.restGet(request, task, **tq.Task.getGraph("default"))


@rd.url(r'^task/hook$')
@rd.url(r'^task/hook/(?P<pk>\d+)$')
@rd.login_required
def rest_on_tasklog(request, pk=None):
    return tq.TaskHook.on_rest_request(request, pk)


@rd.url(r'^task/hook/test$')
@rd.perm_required("manage_hooks")
def rest_on_task_hook_test(request):
    hook = request.DATA.get("hook", None)
    if not hook:
        return rv.restStatus(request, False, error="Hook attributes required.")
    data = request.DATA.get("data", None)
    when = request.DATA.get("when", None)
    props = request.DATA.get("props", None)
    category = request.DATA.get("category", None)
    hook = tq.TaskHook(**hook)
    if props:
        hook.save()
        hook.setProperties(props, category=category)
        task = hook.trigger(data, when)
        hook.delete()
    else:
        task = hook.trigger(data, when)
    return rv.restGet(request, task, **tq.Task.getGraph("default"))


@rd.url(r'^restart$')
@rd.perm_required("manage_staff")
def rest_on_restart(request):
    rest_helpers.log_print("{} request task engine restart".format(request.member.username))
    tq.Task.RestartEngine()
    return rv.restStatus(request, True)


@rd.url(r'^test$')
@rd.perm_required("manage_staff")
def rest_on_test(request):
    tq.Task.PublishTest(request.DATA.get("test_count", 1, field_type=int), request.DATA.get("sleep_time", 10.0, field_type=float))
    return rv.restStatus(request, True)


@rd.url(r'^task/status$')
def rest_on_task_status(request):
    out = UberDict()
    last_completed = tq.Task.objects.filter(state=tq.TASK_STATE_COMPLETED).last()
    if last_completed:
        out.last_completed = last_completed.completed_at
    last_scheduled = tq.Task.objects.all().last()
    if last_scheduled:
        out.last_scheduled = last_scheduled.created
    stale = datetime.now() - timedelta(minutes=request.DATA.get("minutes_back", 60))
    qset = tq.Task.objects.filter(modified__gte=stale)
    out.total = qset.count()
    out.running = qset.filter(state=tq.TASK_STATE_STARTED).count()
    out.backlog = qset.filter(state=tq.TASK_STATE_SCHEDULED).count()
    out.completed = qset.filter(state=tq.TASK_STATE_COMPLETED).count()
    out.failed = qset.filter(state=tq.TASK_STATE_FAILED).count()
    out.retry = qset.filter(state=tq.TASK_STATE_RETRY).count()
    return rv.restGet(request, out)


@rd.url(r'^task/stats$')
def rest_on_stats(request):
    when = datetime.now() - timedelta(days=7)
    report = (tq.Task.objects.filter(
        created__gte=when)
        .annotate(day=Trunc('created', 'day'))
        .values('day')
        .annotate(running=Count('state', filter=Q(state=tq.TASK_STATE_STARTED)))
        .annotate(backlog=Count('state', filter=Q(state=tq.TASK_STATE_SCHEDULED)))
        .annotate(completed=Count('state', filter=Q(state=10)))
        .annotate(failed=Count('state', filter=Q(state=-1)))
        .annotate(longest=Max('runtime')))
    return rv.restGet(request, dict(stats=list(report)))


@rd.url(r'^test/webrequest$')
def rest_on_webrequest(request):
    msg = "Successfully received the following data\n{}".format(str(request.DATA.toDict()))
    return rv.restStatus(request, True, msg=msg)
