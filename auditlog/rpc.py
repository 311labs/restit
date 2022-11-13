from . import models as auditlog

from rest import views as rv
from rest import decorators as rd


@rd.url(r'^plog$')
@rd.url(r'^plog/(?P<plog_id>\d+)$')
@rd.perm_required('view_logs')
def plog_handler(request, plog_id=None):
    if not plog_id:
        min_pk = getattr(auditlog.settings, "PLOG_STALE_ID", 0)
        return auditlog.PersistentLog.on_rest_list(request, qset=auditlog.PersistentLog.objects.filter(pk__gte=min_pk))
    return auditlog.PersistentLog.on_rest_request(request, plog_id)


@rd.urlGET(r'^plog_old$')
@rd.perm_required('view_logs')
def plogList(request):
    auditlog.PersistentLog.on_request_handle()

    graph = request.DATA.get("graph", "default")
    qset = auditlog.PersistentLog.objects.all()
    if request.group:
        qset = qset.filter(group=request.group)

    ip = request.DATA.get("ip")
    if ip:
        qset = qset.filter(session__ip=ip)

    path = request.DATA.get("path")
    if path:
        qset = qset.filter(remote_path__icontains=path)
    
    method = request.DATA.get("method")
    if method:
        qset = qset.filter(method=method)

    action = request.DATA.get("action")
    if action:
        qset = qset.filter(action=action)
    
    component = request.DATA.get("component")
    if component:
        qset = qset.filter(component=component)
    
    pkey = request.DATA.get("pkey")
    if pkey:
        qset = qset.filter(pkey=pkey)

    username = request.DATA.get("username")
    if username:
        qset = qset.filter(user__username=username)
    
    term = request.DATA.get("term")
    if term:
        qset = qset.filter(message__icontains=term)
    
    return rv.restList(request, qset.order_by('-when'), **auditlog.PersistentLog.getGraph(graph))


@rd.urlGET (r'^list$')
def auditList(request):
    """
    | Parameter: model=<string> (default=all)
    | Parameter: id=<int> (default=all)
    | Parameter: attributes=<string> (default=all)
    | Parameter: user=<id|username> (default=all)
    |
    | Return: audit log entries
    """
    ret = auditlog.AuditLog.objects.all()
    
    model = request.DATA.get('model')
    if model:
        ret = ret.filter(model=model)

    id = request.DATA.get('id')
    if id:
        ret = ret.filter(pkey=int(id))

    attributes = request.DATA.get('attributes')
    if attributes:
        attributes = attributes.split(',')
        print(attributes)
        ret = ret.filter(attribute__in=attributes)

    user = request.DATA.get('user')
    if user:
        ret = ret.filter(user=user)

    return rv.restList(
        request, ret, sort='-when',
        fields=(
            'when',
            'model',
            'pkey',
            'attribute',
            'user.id',
            'user.username',
            'reference',
            'how',
            'referer',
            'stack',
            'oldval',
            'newval',
        ), recurse_into=(
            'user',
        ), require_perms=(
            'auditlog.can_read',
        ),
    )


@rd.url(r'^nuke$')
@rd.perm_required("nuke_logs")
def nuke_log_data(request):
    # nuclear option used for testing system to clear out all wallet data
    # make sure this is enabled for this setup
    confirm_nuke = request.DATA.get("nuke_code", None)
    if confirm_nuke != "launch" or not getattr(auditlog.settings, "CAN_NUKE_DATABASE", False):
        return rv.restPermissionDenied(request)

    # first nuke all transactions
    auditlog.PersistentLog.objects.all().delete()
    auditlog.AuditLog.objects.all().delete()
    auditlog.SessionLog.objects.all().delete()
    return rv.restStatus(request, True)
