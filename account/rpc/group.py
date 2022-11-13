from rest import decorators as rd
from rest import views as rv
from account.models import Group, Membership, Member
from taskqueue import models as tq

@rd.url(r'^group$')
@rd.url(r'^group/$')  # required for legacy support
@rd.url(r'^group/(?P<pk>\d+)$')
@rd.login_required
def rest_on_group(request, pk=None):
    return Group.on_rest_request(request, pk)


@rd.urlGET(r'^member/groups$')
@rd.login_required
def member_groups(request):
    member_id = request.DATA.get(["member", "member_id"])
    if not member_id:
        return rv.restPermissionDenied(request)
    member = Member.objects.filter(pk=member_id).last()
    return Group.on_rest_list(request, member.getGroups())


@rd.url(r'^group/invite$')
@rd.url(r'^group/invite/(?P<group_id>\d+)$')
@rd.perm_required(["manage_members", "invite_members", "manage_groups"])
def rest_on_group_invite(request, group_id=None):
    if group_id:
        group = Group.objects.filter(pk=group_id).first()
        if not group:
            return rv.restPermissionDenied(request)
    else:
        group = request.group
    if group is None:
        return rv.restPermissionDenied(request, "requires group")
    # this will throw exception on failure
    ms = None
    member = None
    member_id = request.DATA.get(["member", "member_id"])
    if member_id:
        member = Member.objects.filter(pk=member_id).last()
    btn_label = "VIEW NOW"
    is_new = member is None
    if member is None:
        btn_label = "REGISTER"
        # create new member, but only allow basic information
        data = request.DATA.fromKeys(["username", "email", "phone_number", "display_name", "first_name", "last_name"])
        if not data or not data.email:
            return rv.restPermissionDenied(request, "missing fields")
        if data.email:
            member = Member.GetMember(data.email.lower())
        elif data.username:
            member = Member.GetMember(data.username)
        elif data.phone_number:
            member = Member.GetMemberByPhone(data.phone_number)
        if member is None:
            member = Member.createFromDict(request, data)
    ms = group.invite(member, request.DATA.get("role", "guest"))
    ms.sendInvite(request)
    return ms.restGet(request)


@rd.url(r'^membership$')
@rd.url(r'^membership/(?P<pk>\d+)$')
@rd.login_required
def rest_on_membership(request, pk=None):
    return Membership.on_rest_request(request, pk)


@rd.url(r'^membership/group/(?P<group_id>\d+)$')
@rd.url(r'^membership/me-(?P<group_id>\d+)$')
@rd.login_required
def rest_on_users_membership(request, group_id=None):
    ms = request.member.getMembershipFor(group_id, include_parents=True)
    if ms is None:
        return rv.restStatus(request, False, error="not found", error_code=404)
    return ms.restGet(request)

# LEGACY SUPPORT
@rd.urlPOST(r'^group/apply/children/setting$')
@rd.perm_required("manage_groups")
def apply_children_setting(request):
    if not request.group:
        return rv.restStatus(request, False, error="Group is required.")
    setting = request.DATA.get("setting", None)
    value = request.DATA.get("value", None)
    if not setting or not value:
        return rv.restStatus(request, False, error="Both setting and value are required.")
    task = tq.Task.Publish("payauth", "on_background_job", {
        "bg_handler": "apply_children_setting",
        "setting": setting,
        "value": value,
        "group_id": request.group.id
    }, channel="tq_app_handler_update")
    return rv.restStatus(request, True, msg="Task has been scheduled!")
