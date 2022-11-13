# from .models import *
# from .forms import *

# from django.shortcuts import get_object_or_404, Http404
# from account.models import User
# from django.db.models import Q

# from rest.views import *
# from rest.decorators import *
# from rest import helpers

# from django.conf import settings

# def medialib_setting(view_func, var, dflt=None):
#     def _wrapper_en(request, *args, **kwargs):
#         return view_func(request, *args, **kwargs)
#     def _wrapper_dis(request, *args, **kwargs):
#         u = getattr(request, 'user')
#         if not u.is_staff:
#             raise Http404
#         return view_func(request, *args, **kwargs)

#     if getattr(settings, var, dflt):
#         return _wrapper_en
#     else:
#         return _wrapper_dis

# def medialib_manage(view_func):
#     return medialib_setting(view_func, 'MEDIALIB_MANAGE_ENABLE')
# def medialib_edit(view_func):
#     return medialib_setting(view_func, 'MEDIALIB_EDIT_ENABLE')

# @urlGET (r'^library/$')
# @vary_on_cookie
# @cache_control(private=True, max_age=300)
# def mediaLibraryList(request):
#     """
#     | Parameters:
#     |	owner: <me|id|username>

#     | Return: REST list of all MediaLibrary data

#     | List all media libraries the user can use
#     """
#     if 'owner' in request.DATA:
#         ids = []
#         for u in request.DATA['owner'].split(","):
#             try:
#                 if u == "me" and request.user and request.user.is_authenticated:
#                     ids.append(str(request.user.id))
#                 elif u.isdigit():
#                     ids.append(str(User.objects.get(id=u).id))
#                 else:
#                     ids.append(str(User.objects.get(username=u).id))
#             except User.DoesNotExist:
#                 raise InternalError("No such user: %s" % u)
#         ret = MediaLibrary.objects.filter(owner__in=ids)
#     elif request.user.has_perm('medialib.can_manage'):
#         ret = MediaLibrary.objects.all()
#     else:
#         ret = MediaLibrary.listPermitted("L", request.user)

#     if 'kind' in request.DATA:
#         ret = ret.filter(Q(allowed_kinds__isnull = True) | Q(allowed_kinds__contains = request.DATA['kind']))

#     return restList(request, ret, exclude=(
#         'allowed_kinds',
#     ), extra=(
#         ('allowed_kinds_list', 'allowed_kinds'),
#     ))


# @urlGET (r'^library/(?P<library_id>\d+)$')
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryGet(request, library_id):
#     """
#     | Get information about specified media library
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("L", request.user)
#     rset = list(lib.rendition_sets.all())
#     defs = RenditionSet.objects.filter(default_set=True)
#     for d in defs:
#         found = False
#         for r in rset:
#             if r.kind == d.kind:
#                 found = True
#                 break
#         if not found:
#             rset.append(d)
#     lib.__rendition_sets = rset
#     return restGet(request, lib, recurse_into=(
#         ('__rendition_sets', 'rendition_sets',),
#     ), exclude=(
#         'rendition_sets.id',
#         'allowed_kinds',
#     ), extra=(
#         ('allowed_kinds_list', 'allowed_kinds'),
#     ))

# @urlGET (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionSetGet(request, library_id, kind):
#     """
#     | Get specifics about a rendition set for a library
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("L", request.user)
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         rset = get_object_or_404(RenditionSet, default_set=True, kind=kind)

#     return restGet(request, rset, recurse_into=(
#         'renditions',
#         ('renditions.preset', ''),
#     ), fields=(
#         'default_set',
#         'kind',
#         'name',
#         'renditions.active',
#         'renditions.id',
#         'renditions.description',
#         'renditions.name',
#         'renditions.use',
#         ('renditions.preset.name', 'preset_name',),
#     ))

# def _copyRenditionSet(old, into, lib):
#     """
#     | make a copy of a rendition set (useful for copying default for customization)
#     """
#     if into:
#         rset = into
#     else:
#         rset = RenditionSet(kind=old.kind, default_set=False, name=old.name)
#     if not rset.id:
#         rset.save()
#     for r in old.renditions.all():
#         rn = RenditionDefinition(name=r.name, description=r.description, preset=r.preset, active=r.active, use=r.use)
#         rn.save()
#         rset.renditions.add(rn)
#         for p in RenditionDefinitionParameterSetting.objects.filter(renditionDefinition=r):
#             pn = RenditionDefinitionParameterSetting(renditionDefinition=rn, parameter=p.parameter, setting=p.setting)
#             pn.save()
#     lib.rendition_sets.add(rset)
#     return rset

# def _getRendition(rset, dflt, kind, rendition_id):
#     try:
#         return rset.renditions.get(pk = rendition_id)
#     except RenditionDefinition.DoesNotExist:
#         if not dflt:
#             dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         try:
#             rendition = dflt.renditions.get(pk = rendition_id)
#         except RenditionDefinition.DoesNotExist:
#             raise Http404
#         try:
#             return rset.renditions.get(name = rendition.name)
#         except RenditionDefinition.DoesNotExist:
#             raise Http404


# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionSetChange(request, library_id, kind):
#     """
#     | Update rendition set for a library
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     is_new = False
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         rset = RenditionSet(kind=kind, default_set=False, name="new_rendition_set")
#         is_new = True

#     if rset.default_set and not request.user.is_staff:
#         raise InternalError("Cannot edit default set")

#     ret = restSet(request, rset, form=RenditionSetForm)
#     if is_new and rset.id:
#         _copyRenditionSet(dflt, rset, lib)
#     return ret

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/reset$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionSetReset(request, library_id, kind):
#     """
#     | reset rendition set to default
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)

#     for rs in lib.rendition_sets.filter(kind=kind):
#         if rs.default_set and not request.user.is_staff:
#             raise InternalError("Cannot edit default set")
#         rs.renditions.all().delete()
#     lib.rendition_sets.filter(kind=kind).delete()
#     return restStatus(request, True)

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/clear$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionSetClear(request, library_id, kind):
#     """
#     | clear all renditions from rendition set
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         rset = RenditionSet(kind=kind, default_set=False, name=dflt.name)
#         rset.save()
#         lib.rendition_sets.add(rset)

#     if rset.default_set and not request.user.is_staff:
#         raise InternalError("Cannot edit default set")

#     rset.renditions.all().delete()

#     return restStatus(request, True)

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/add$')
# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionEdit(request, library_id, kind, rendition_id=None):
#     """
#     | add new or edit rendition
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         rset = _copyRenditionSet(dflt, None, lib)

#     if rset.default_set and not request.user.is_staff:
#         raise InternalError("Cannot edit default set")

#     if rendition_id:
#         rendition = _getRendition(rset, dflt, kind, rendition_id)
#     else:
#         rendition = None

#     (ret, nrendition) = restSet(request, rendition, form=RenditionDefinitionForm, return_object=True)

#     if not rendition:
#         rset.renditions.add(nrendition)

#     return ret

# @urlDELETE (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionDelete(request, library_id, kind, rendition_id):
#     """
#     | delete rendition
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         rset = _copyRenditionSet(dflt, None, lib)

#     if rset.default_set and not request.user.is_staff:
#         raise InternalError("Cannot edit default set")

#     rendition = _getRendition(rset, dflt, kind, rendition_id)
#     rendition.delete()

#     return restStatus(request, True)

# @urlGET (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionGet(request, library_id, kind, rendition_id):
#     """
#     | Get rendition setttings
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         rset = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#     rendition = _getRendition(rset, None, kind, rendition_id)

#     params = {}
#     for p in rendition.preset.configurable_parameters.all():
#         params[p.name] = (p, None, True)
#     rp = rendition.getParameters()
#     for name in rp:
#         if name in params:
#             params[name] = (rp[name][0], rp[name][1], rp[name][2])
#     rendition.__config = list(RenditionDefinitionParameterSetting(parameter=p, setting=v, default=d) for (k, (p, v, d)) in sorted(params.items()))

#     return restGet(request, rendition, recurse_into=(
#         ('preset', ''),
#         ('__config', 'config',),
#         ('config.parameter', '',),
#         'configSet',
#     ), fields=(
#         'active',
#         'id',
#         'description',
#         'name',
#         'use',
#         ('preset.name', 'preset_name',),
#         'config.setting',
#         'config.default',
#         'config.parameter.name',
#         'config.parameter.required',
#         'config.parameter.kind',
#         'config.parameter.description',
#         'config.parameter.choices',
#         'configSet.id',
#         'configSet.name',
#     ))

# @urlGET (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)/(?P<config_name>\w+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionGetSetting(request, library_id, kind, rendition_id, config_name):
#     """
#     | Get rendition setttings
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         rset = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#     rendition = _getRendition(rset, None, kind, rendition_id)

#     p = get_object_or_404(RenditionParameter, name=config_name)
#     p.__setting = rendition.getParameter(p)

#     return restGet(request, p, fields=(
#         ('__setting', 'setting',),
#         'name',
#         'required',
#         'kind',
#         'description',
#         'choices',
#     ))

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)/(?P<config_name>\w+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionSetSetting(request, library_id, kind, rendition_id, config_name):
#     """
#     | Set rendition setttings
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         rset = _copyRenditionSet(dflt, None, lib)
#     rendition = _getRendition(rset, dflt, kind, rendition_id)

#     p = get_object_or_404(RenditionParameter, name=config_name)
#     try:
#         setting = p.validate_setting(request.DATA.get('setting', None))
#     except ValueError as e:
#         return restStatus(request, False, error=e.message, errors={"setting": e.message})

#     (cfg, _) = RenditionDefinitionParameterSetting.objects.get_or_create(renditionDefinition=rendition, parameter=p)
#     cfg.setting = setting
#     cfg.save()
#     return restStatus(request, True)

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)/(?P<config_name>\w+)/reset$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionResetSetting(request, library_id, kind, rendition_id, config_name):
#     """
#     | Set rendition setttings
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         return restStatus(request, True)
#     rendition = _getRendition(rset, dflt, kind, rendition_id)

#     p = get_object_or_404(RenditionParameter, name=config_name)
#     RenditionDefinitionParameterSetting.objects.filter(renditionDefinition=rendition, parameter=p).delete()
#     return restStatus(request, True)

# @urlPOST (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)/accountConfig/(?P<cfg_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionAddAccountConfig(request, library_id, kind, rendition_id, cfg_id):
#     """
#     | Add account config to media lib rendition def
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         return restStatus(request, True)
#     rendition = _getRendition(rset, dflt, kind, rendition_id)

#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("R", request.user)

#     rendition.configSet.add(cfg);

#     return restStatus(request, True)

# @urlDELETE (r'^library/(?P<library_id>\d+)/renditionset/(?P<kind>.)/(?P<rendition_id>\d+)/accountConfig/(?P<cfg_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaLibraryRenditionDeleteAccountConfig(request, library_id, kind, rendition_id, cfg_id):
#     """
#     | Add account config to media lib rendition def
#     """
#     lib = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         lib.assertAcl("A", request.user)
#     dflt = None
#     try:
#         rset = lib.rendition_sets.get(kind=kind)
#     except RenditionSet.DoesNotExist:
#         dflt = get_object_or_404(RenditionSet, default_set=True, kind=kind)
#         return restStatus(request, True)
#     rendition = _getRendition(rset, dflt, kind, rendition_id)

#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("R", request.user)

#     rendition.configSet.remove(cfg);

#     return restStatus(request, True)


# @urlGET (r'^library/(?P<library_id>\d+)/items$')
# @vary_on_cookie
# @cache_control(private=True, max_age=300)
# def mediaLibraryGetItems(request, library_id):
#     """
#     | Get items inside a media library
#     """
#     ret = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         ret.assertAcl("L", request.user)
#     fields=["id", "kind", "library", "name", "description", "state", "render_error", "created", "owner.username", "owner.id"]
#     ret = ret.items.all()
#     if 'kind' in request.DATA:
#         ret = ret.filter(kind__in = request.DATA['kind'].split(","))
#     return restList(request, ret, fields=fields, recurse_into=["owner"])

# @urlPOST (r'^library/(?P<library_id>\d+)$')
# @medialib_manage
# def mediaLibrarySet(request, library_id):
#     """
#     | Update media library metadata
#     """
#     ret = get_object_or_404(MediaLibrary, pk=library_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         ret.assertAcl("W", request.user)
#     return restSet(request, ret, form=MediaLibraryForm)

# @urlGET (r'^item/(?P<item_id>\d+)/renditions$')
# @urlGET (r'^item/(?P<item_id>\d+)\.(?P<token>[^/]*)/renditions$')
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def mediaItemGetRenditions(request, item_id, token=None):
#     """
#     | Get information about specified media item
#     """
#     item = get_object_or_404(MediaItem, pk=item_id)
#     if not item.check_token(token):
#         if not request.user.has_perm('medialib.can_manage'):
#             item.assertAcl("R", request.user)

#     return _mediaItemGetRenditions(request, item)

# def _mediaItemGetRenditions(request, item, accept_list=None):
#     """
#     | Get information about specified media item
#     """
#     renditions = item.renditions.all()
#     if request.DATA.get('use', None):
#         renditions = renditions.filter(use = request.DATA['use'])
#     for f in ('height', 'width', 'bytes', 'created'):
#         if request.DATA.get(f, None):
#             renditions = renditions.filter(**{ f: request.DATA[f] })
#         elif request.DATA.get(f + "_gt", None):
#             renditions = renditions.filter(**{ f+"__gt": request.DATA[f] })
#         elif request.DATA.get(f + "_lt", None):
#             renditions = renditions.filter(**{ f+"__lt": request.DATA[f] })
#     renditions = renditions.order_by('-created')

#     rseen = []
#     ret = []
#     for r in renditions:
#         if r.rendition_definition_id in rseen:
#             continue
#         rseen.append(r.rendition_definition_id)
#         ret.append(r)

#     def cmp_rendition(x, y):
#         r = cmp(x.use, y.use)
#         if r != 0:
#             return r
#         r = cmp(x.bytes, y.bytes)
#         if r != 0:
#             return r
#         r = cmp(x.rendition_definition_id, y.rendition_definition_id)
#         if r != 0:
#             return r
#         r = cmp(x.pk, y.pk)
#         return r
#     ret.sort(cmp=cmp_rendition)

#     return restList(request, ret, size=0, model=MediaItemRendition, exclude=['mediaitem', 'url', 'rendition_definition'], extra=[('view_url', 'url'), ('rtmp_url', 'rtmp')], accept_list=accept_list);

# @urlGET (r'^item/(?P<item_id>\d+)$')
# @urlGET (r'^item/(?P<item_id>\d+)\.(?P<token>[^/]*)$')
# @vary_on_cookie
# @cache_control(private=True, max_age=300)
# def mediaItemGet(request, item_id, token=None):
#     """
#     | Get information about specified media item
#     """
#     ret = get_object_or_404(MediaItem, pk=item_id)
#     if not ret.check_token(token):
#         if not request.user.has_perm('medialib.can_manage'):
#             ret.assertAcl("R", request.user)
#     opts = {
#         'recurse_into': (('cuepoint', 'cuepoints',),),
#     }
#     if ret.kind == 'L':
#         opts['extra'] = (('live_state_ingesting','stream_ingesting',), )
#     data = restGet(request, ret, exclude=['acl_is_default'], accept_list=['data'], **opts)
#     data['renditions'] = _mediaItemGetRenditions(request, ret, accept_list=['data'])
#     return restReturn(request, data)

# @urlPOST (r'^item/(?P<item_id>\d+)/stop$')
# @vary_on_cookie
# def mediaItemStop(request, item_id):
#     """
#     | stop ingesting
#     """
#     item = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         item.assertAcl("W", request.user)
#     if not item.live_state_ingesting():
#         return restStatus(request, False, error="Not actively ingesting")
#     item.state = 120
#     item.save()
#     return restStatus(request, True)

# @urlPOST (r'^item/(?P<item_id>\d+)$')
# @medialib_edit
# def mediaItemSet(request, item_id):
#     """
#     | Update information about specified media item
#     """
#     ret = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         ret.assertAcl("W", request.user)
#     return restSet(request, ret, form=MediaItemCanUploadForm)

# @urlDELETE (r'^item/(?P<item_id>\d+)$')
# @medialib_edit
# def mediaItemDelete(request, item_id):
#     """
#     | Delete specified media library
#     """
#     ret = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         ret.assertAcl("D", request.user)
#     return restDelete(request, ret)


# @urlPOST (r'^library/_/new$')
# @urlPOST (r'^library/(?P<library_id>\d+)/new$')
# @medialib_edit
# def mediaItemNew(request, library_id=None):
#     """
#     | Upload new media item
#     """
#     ret = None
#     if library_id:
#         ret = get_object_or_404(MediaLibrary, pk=library_id)
#         if not request.user.has_perm('medialib.can_manage'):
#             ret.assertAcl("C", request.user)

#     if not ret:
#         if request.user and request.user.is_authenticated:
#             try:
#                 ret = MediaLibrary.objects.filter(owner=request.user)[0]
#             except IndexError:
#                 pass

#     if not ret:
#         try:
#             ret = MediaLibrary.listPermitted('C', request.user)[0]
#         except IndexError:
#             pass

#     if not ret:
#         ret = MediaLibrary(name='Default Library', owner=request.user)
#         ret.save()

#     return restAdd(request, {}, form=MediaItemUploadForm, data_override={ 'library': ret })

# @url (r'^renditionPreset$')
# @medialib_manage
# def listRenditionPresets(request):
#     """
#     | List available presets
#     """
#     return restList(request, RenditionPreset.objects.all(), fields=(
#         'name',
#         'short_name',
#         'description',
#         'stage',
#         'is_distribution',
#         'configurable_parameters.name',
#         'configurable_parameters.description',
#         'configurable_parameters.required',
#         'configurable_parameters.kind',
#         'configurable_parameters.choices',
#     ), recurse_into=(
#         "configurable_parameters",
#     ))

# @url (r'^renditionPreset/(?P<name>\w+)$')
# @medialib_manage
# def getRenditionPresets(request, name):
#     """
#     | Get presets info
#     """
#     ret = get_object_or_404(MediaLibrary, short_name=name)
#     return restGet(request, ret, fields=(
#         'name',
#         'short_name',
#         'description',
#         'stage',
#         'is_distribution',
#         'configurable_parameters.name',
#         'configurable_parameters.description',
#         'configurable_parameters.required',
#         'configurable_parameters.kind',
#         'configurable_parameters.choices',
#     ), recurse_into=(
#         "configurable_parameters",
#     ))

# @urlGET (r'^accountConfig$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigList(request):
#     """
#     | Parameters:
#     |	owner: <me|id|username>

#     | Return: REST list of account configs

#     | List available account config sets
#     """
#     if 'owner' in request.DATA:
#         ids = []
#         for u in request.DATA.get('owner', 'me').split(","):
#             try:
#                 if u == "me" and request.user and request.user.is_authenticated:
#                     ids.append(str(request.user.id))
#                 elif u.isdigit():
#                     ids.append(str(User.objects.get(id=u).id))
#                 else:
#                     ids.append(str(User.objects.get(username=u).id))
#             except User.DoesNotExist:
#                 raise InternalError("No such user: %s" % u)
#         ret = AccountConfig.objects.filter(owner__in = ids)
#     else:
#         ret = AccountConfig.listPermitted("L", request.user)

#     if 'applicable_preset' in request.DATA:
#         try:
#             if request.DATA['applicable_preset']:
#                 preset = RenditionPreset.objects.get(short_name = request.DATA['applicable_preset'])
#             else:
#                 preset = None
#         except RenditionPreset.DoesNotExist:
#             return restStatus(request, False, error="Preset not found: %s" % preset, errors={"applicable_preset": "Preset not found: %s" % preset})
#         ret = ret.filter(applicable_preset = preset)

#     return restList(request, ret, fields=(
#         'id',
#         'name',
#         ('!applicable_preset.name', 'applicable_preset',),
#         ('!owner.username', 'owner',),
#     ))

# @urlPOST (r'^accountConfig/(?P<cfg_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigEdit(request, cfg_id):
#     """
#     | Parameters:
#     |	name: <string>
#     |	applicable_preset: <string>

#     | add/edit accountConfig
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)

#     if 'name' in request.DATA:
#         cfg.name = request.DATA['name']
#     if 'applicable_preset' in request.DATA:
#         preset = request.DATA['applicable_preset']
#         try:
#             cfg.applicable_preset = RenditionPreset.objects.get(short_name = preset)
#         except RenditionPreset.DoesNotExist:
#             return restStatus(request, False, error="Preset not found: %s" % preset, errors={"applicable_preset": "Preset not found: %s" % preset})
#     cfg.save()
#     return restStatus(request, True, id=cfg.id)

# @urlDELETE (r'^accountConfig/(?P<cfg_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigDelete(request, cfg_id):
#     """
#     | Parameters: NONE

#     | delete accountConfig
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("D", request.user)
#     cfg.delete()
#     return restStatus(request, True)

# @urlGET (r'^accountConfig/(?P<cfg_id>\d+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigGet(request, cfg_id):
#     """
#     | Parameters: NONE

#     | Return: account config details

#     | Get account config by id
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("R", request.user)

#     params = {}
#     for p in AccountConfigParameterSetting.objects.filter(accountConfig=cfg):
#         params[p.parameter.name] = (p.parameter, p.setting)
#     cfg.__config = list(RenditionDefinitionParameterSetting(parameter=p, setting=v) for (k, (p, v)) in list(params.items()))

#     return restGet(request, cfg, recurse_into=(
#         ('__config', 'config',),
#         ('config.parameter', '',),
#     ), fields=(
#         'id',
#         'name',
#         ('!owner.username', 'owner',),
#         ('!applicable_preset.name', 'applicable_preset',),
#         'config.setting',
#         'config.parameter.name',
#         'config.parameter.required',
#         'config.parameter.kind',
#         'config.parameter.description',
#         'config.parameter.choices',
#     ))

# @urlGET (r'^accountConfig/(?P<cfg_id>\d+)/(?P<config_name>\w+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigParameterGet(request, cfg_id, config_name):
#     """
#     | Parameters: NONE

#     | Return: account config details

#     | Get account config by id
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("R", request.user)
#     ret = get_object_or_404(AccountConfigParameterSetting, accountConfig=cfg, parameter__name=config_name)

#     return restGet(request, ret, recurse_into=(
#         ('parameter', '',),
#     ), fields=(
#         'setting',
#         'parameter.name',
#         'parameter.required',
#         'parameter.kind',
#         'parameter.description',
#         'parameter.choices',
#     ))

# @urlPOST (r'^accountConfig/(?P<cfg_id>\d+)/(?P<config_name>\w+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigParameterSet(request, cfg_id, config_name):
#     """
#     | Parameters: NONE

#     | Return: account config details

#     | Get account config by id
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("C", request.user)
#     p = get_object_or_404(RenditionParameter, name=config_name)

#     try:
#         setting = p.validate_setting(request.DATA.get('setting', None))
#     except ValueError as e:
#         return restStatus(request, False, error=e.message, errors={"setting": e.message})

#     (s, _) = AccountConfigParameterSetting.objects.get_or_create(accountConfig=cfg, parameter=p)
#     s.setting = setting
#     s.save()
#     return restStatus(request, True)

# @urlDELETE (r'^accountConfig/(?P<cfg_id>\d+)/(?P<config_name>\w+)$')
# @medialib_manage
# @vary_on_cookie
# @cache_control(private=True, max_age=1)
# def accountConfigParameterDel(request, cfg_id, config_name):
#     """
#     | Parameters: NONE

#     | Return: account config details

#     | Get account config by id
#     """
#     cfg = get_object_or_404(AccountConfig, pk=cfg_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         cfg.assertAcl("C", request.user)
#     p = get_object_or_404(RenditionParameter, name=config_name)

#     try:
#         setting = p.validate_setting(request.DATA.get('setting', None))
#     except ValueError as e:
#         return restStatus(request, False, error=e.message, errors={"setting": e.message})

#     s = get_object_or_404(AccountConfigParameterSetting, accountConfig=cfg, parameter=p)
#     s.delete()
#     return restStatus(request, True)

# @urlGET (r'^item/(?P<item_id>\d+)/cue$')
# def mediaItemCueList(request, item_id):
#     ret = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         ret.assertAcl("R", request.user)

#     return restList(request, ret.cuepoint_set.all())

# @urlPOST (r'^item/(?P<item_id>\d+)/cue$')
# @urlPOST (r'^item/(?P<item_id>\d+)/cue/(?P<cue_id>\d+)$')
# @medialib_edit
# def mediaItemCueSet(request, item_id, cue_id=None):
#     """
#     | Update information about specified media item
#     """
#     item = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         item.assertAcl("W", request.user)
#     if not item.kind in ('V', 'L', 'A'):
#         return restStatus(request, False, error="Can only cue video assets")

#     if cue_id:
#         cue = get_object_or_404(CuePoint, pk=item_id, item=item)
#     else:
#         cue = None

#     return restSet(request, cue, form=CuePointForm, formopts={"item": item})

# @urlDELETE (r'^item/(?P<item_id>\d+)/cue/(?P<cue_id>\d+)$')
# @medialib_edit
# def mediaItemCueDel(request, item_id, cue_id):
#     """
#     | Update information about specified media item
#     """
#     item = get_object_or_404(MediaItem, pk=item_id)
#     if not request.user.has_perm('medialib.can_manage'):
#         item.assertAcl("W", request.user)
#     if not item.kind in ('V', 'L', 'A'):
#         return restStatus(request, False, error="Can only cue video assets")

#     cue = get_object_or_404(CuePoint, pk=item_id, item=item)

#     return restDelete(request, cue)

# @urlGET (r'^item/search$')
# def mediaItemSearchl(request):
#     """
#     | Parameters:
#     |	q: string
#     """
#     if request.user.has_perm('medialib.can_manage'):
#         ret = MediaItem.objects.filter(state=200)
#     else:
#         ret = MediaItem.listPermitted('L', request.user).filter(state=200)

#     for q in request.DATA.get('q', '').split(' '):
#         ret = ret.filter(Q(name__icontains=q) | Q(library__name__icontains=q) | Q(owner__username__icontains=q) | Q(owner__first_name__icontains=q) | Q(owner__last_name__icontains=q))

#     return restList(request, ret,
#         fields=(
#             "id",
#             "kind",
#             "library",
#             "name",
#             "description",
#             "state",
#             "created",
#             "owner.username",
#             "owner.id",
#             ("!thumbnail_large.view_url", "thumbnail"),
#             ("!image_small.view_url", "image"),
#             ("!thumbnail_animated.view_url", "thumbnail_animated"),
#             ("still.view_url_nonexpire", "still"),
#             ("still.width", "width"),
#             ("still.height", "height"),
#         ),
#         recurse_into=(
#             "owner",
#             ("still",''),
#         ),
#     )

# def saveMediaFile(file, name, file_name=None, is_base64=False):
#     """
#     Generic method to save a media file
#     """
#     if file_name is None:
#         file_name = name
#     # make sure we set the name base64_data
#     if is_base64:
#         mi = MediaItem(name=file_name, base64_data=file)
#     elif type(file) in [str, str] and (file.startswith("https:") or file.startswith("http:")):
#         mi = MediaItem(name=name, downloadurl=file)
#     else:
#         mi = MediaItem(name=name, newfile=file)
#     mi.save()
#     return mi

# from . import ocr
# from shutil import copyfile
# @urlPOST(r'^ocr$')
# @urlPOST(r'^ocr/$')
# def ocr_handler(request):
#     if not ocr.hasTesseract():
#         return restPermissionDenied(request, error="tesseract not installed")
#     b64 = request.DATA.get("image")
#     if not b64 and len(request.FILES) == 0:
#         return restPermissionDenied(request, error="no files found")
#     if b64:
#         # print(b64)
#         # print(b64[:64].decode("base64"))
#         img_data = b64.decode('base64')
#         print(("img size: {}".format(len(b64))))
#     else:
#         img_filename = list(request.FILES.keys())[0]
#         img_file = request.FILES[img_filename]
#         img_file.seek(0)
#         img_data = img_file.read()

#     output = ""
#     charset = request.DATA.get("charset", None)
#     pp_dpi = request.DATA.get("pp_dpi", field_type=bool)
#     pp_noise = request.DATA.get("pp_noise", field_type=bool)

#     with helpers.TemporaryFile() as tmp_path:
#         charset = request.DATA.get("charset", None)
#         with open(tmp_path, 'w') as temp:
#             temp.write(img_data)
#             temp.flush()
#         # copyfile(tmp_path, "..../var/ocr.png")
#         output = ocr.ocrImage(tmp_path, pp_dpi=pp_dpi, pp_noise=pp_noise, charset=charset)
#         # copyfile(tmp_path, "..../var/ocr2.png")
#     print("ocr output:")
#     print(output)
#     return restGet(request, {"text":output})



# # BEGIN NEW REST
# @url(r'^media/item/$')
# @url(r'^media/item/(?P<pk>\d+)$')
# @login_required
# def media_item_action(request, pk=None):
#     return MediaItem.on_rest_request(request, pk)

# @url(r'^media/item/ref$')
# @url(r'^media/item/ref/(?P<pk>\d+)$')
# @login_required
# def media_item_action(request, pk=None):
#     return MediaItemRef.on_rest_request(request, pk)


