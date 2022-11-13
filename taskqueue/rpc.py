from rest.views import *
from rest.decorators import *
from rest import search
from rest import helpers as rest_helpers
from rest.uberdict import UberDict
from datetime import datetime, timedelta
from .models import *

@url(r'^task$')
@url(r'^task/(?P<pk>\d+)$')
@login_required
def rest_on_task(request, pk=None):
    return Task.on_rest_request(request, pk)

@url(r'^task/log$')
@url(r'^task/log/(?P<pk>\d+)$')
@login_required
def rest_on_tasklog(request, pk=None):
    return TaskLog.on_rest_request(request, pk)

@url(r'^task/schedule$')
@url(r'^task/schedule/(?P<pk>\d+)$')
@login_required
def rest_on_tasklog(request, pk=None):
    return ScheduledTask.on_rest_request(request, pk)

@urlPOST(r'^task/publish$')
@perm_required("manage_staff")
def rest_on_task_publish(request, pk=None):
    app = request.DATA.get("app").strip()
    module = request.DATA.get("module").strip()
    task_data = request.DATA.get("task_data").strip()
    if not app or not module:
        return restStatus(request, False, error="Both app and module are required.")
    task = Task.Publish(app, module, task_data)
    return restGet(request, task, **Task.getGraph("default"))

@url(r'^task/hook$')
@url(r'^task/hook/(?P<pk>\d+)$')
@login_required
def rest_on_tasklog(request, pk=None):
    return TaskHook.on_rest_request(request, pk)

@url(r'^task/hook/test$')
@perm_required("manage_hooks")
def rest_on_task_hook_test(request):
    hook = request.DATA.get("hook", None)
    if not hook:
        return restStatus(request, False, error="Hook attributes required.")
    data = request.DATA.get("data", None)
    when = request.DATA.get("when", None)
    props = request.DATA.get("props", None)
    category = request.DATA.get("category", None)
    hook = TaskHook(**hook)
    if props:
        hook.save()
        hook.setProperties(props, category=category)
        task = hook.trigger(data, when)
        hook.delete()
    else:
        task = hook.trigger(data, when)
    return restGet(request, task, **Task.getGraph("default"))

@url(r'^restart$')
@perm_required("manage_staff")
def rest_on_restart(request):
    rest_helpers.log_print("{} request task engine restart".format(request.member.username))
    Task.RestartEngine()
    return restStatus(request, True)

@url(r'^test$')
@perm_required("manage_staff")
def rest_on_restart(request):
    Task.PublishTest(request.DATA.get("test_count", 1, field_type=int), request.DATA.get("sleep_time", 10.0, field_type=float))
    return restStatus(request, True)

@url(r'^task/status$')
def rest_on_task_status(request):
    out = UberDict()
    last_completed = Task.objects.filter(state=TASK_STATE_COMPLETED).last()
    if last_completed:
        out.last_completed = last_completed.completed_at
    last_scheduled = Task.objects.all().last()
    if last_scheduled:
        out.last_scheduled = last_scheduled.created
    stale = datetime.now() - timedelta(minutes=request.DATA.get("minutes_back", 60))
    qset = Task.objects.filter(modified__gte=stale)
    out.total = qset.count()
    out.running = qset.filter(state=TASK_STATE_STARTED).count()
    out.backlog = qset.filter(state=TASK_STATE_SCHEDULED).count()
    out.completed = qset.filter(state=TASK_STATE_COMPLETED).count()
    out.failed = qset.filter(state=TASK_STATE_FAILED).count()
    out.retry = qset.filter(state=TASK_STATE_RETRY).count()
    return restGet(request, out)


@url(r'^test/webrequest$')
def rest_on_webrequest(request):
    msg = "Successfully received the following data\n{}".format(str(request.DATA.toDict()))
    return restStatus(request, True, msg=msg)
