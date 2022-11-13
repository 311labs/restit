# from .models import *
from rest import crypto
# from rest.middleware import get_request
from rest import helpers
from rest.uberdict import UberDict
from django.conf import settings
from version import VERSION

from django.db import models
from django.http import HttpResponse, StreamingHttpResponse, Http404
from django.shortcuts import render
from django.db import connection
from django.db.models.query import QuerySet
from django.utils.datastructures import MultiValueDict
# from account.models import User
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q
from django.core.files.uploadedfile import UploadedFile
from io import StringIO

from auditlog.models import PersistentLog

from decimal import Decimal
import math
import datetime
import os
import sys
import types
import time
import pprint
import re
import inspect
import base64
import copy
import json


CHUNKDIR = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'chunked_uploads')


def toJSON(data, **kwargs):
    return json.dumps(data, cls=JSONEncoderExt)
    # return json.dumps(data, **kwargs)

def prettyJSON(data):
    return json.dumps(data, cls=JSONEncoderExt, sort_keys=True, indent=4, separators=(',', ': '))

try:
    import ujson
    def toJSON(data, **kwargs):
        # helpers.log_print(data)
        return ujson.dumps(data)

    # def prettyJSON(data):
    #   return json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
except Exception:
    helpers.log_print("recommend installing ujson!")

# is this useless??? we have rest_serialize
class JSONEncoderExt(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return time.mktime(obj.timetuple())
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y/%m/%d")
        elif isinstance(obj, Decimal):
            if obj.is_nan():
                return 0.0
            return float(obj)
        elif isinstance(obj, float):
            if math.isnan(obj):
                return 0.0
        elif isinstance(obj, set):
            helpers.log_error(obj)
            return str(obj)
        try:
            return super().default(obj)
        except Exception:
            pass
        return "not parsable"


class RawQuery(object):
    def __init__(self, model, distinct=False, returns=None, joins=None, where=None, groupby=None, having=None, sort=None, limit=None, offset=None, count_by=None, last_sort=None, uniques=[]):
        self.model = model
        self.distinct = distinct
        self.returns = returns or []
        self.joins = joins or []
        self.where = where or []
        self.groupby = groupby or []
        self.having = having or []
        self.sort = sort
        self.limit = limit
        self.offset = offset
        self.count_by = count_by
        self.last_sort = last_sort
        self.uniques = uniques

    def addWhere(self, where):
        self.where.append(where)

    def addHaving(self, where):
        self.having.append(where)

    def addJoin(self, model, joinon, jointype=None, joinas=None):
        j = {'model': model, 'joinon': joinon}
        if jointype:
            j['jointype'] = jointype
        if joinas:
            j['joinas'] = joinas
        self.joins.append(j)

    def joined(self, model):
        for j in self.joins:
            if j['model'] == model:
                return True
        return False

    def count(self):
        count_by = self.count_by or '*'
        q = RawQuery(model=self.model, distinct=self.distinct, returns=["COUNT(%s)" % count_by], joins=self.joins, where=self.where, groupby=self.groupby, having=self.having)
        return q.run_raw()[0]

    def sortlist(self):
        if not type(self.sort) in (list,tuple):
            osort = [self.sort, self.last_sort]
        else:
            osort = list(self.sort) + [self.last_sort]
        try:
            osort.remove(None)
        except ValueError:
            pass
        return osort

    def reverse(self):
        osort = self.sortlist()
        self.sort = []
        for s in osort:
            if s[0] == '-':
                s = '+' + s[1:]
            elif s[0] == '+':
                s = '-' + s[1:]
            else:
                s = '-' + s
            self.sort.append(s)
        return self

    def serialize_datetime(self, when):
        if connection.vendor == "mysql":
            return 'FROM_UNIXTIME(%f)' % time.mktime(when.timetuple())
        elif connection.vendor == "postgresql":
            return "(TIMESTAMP WITH TIME ZONE 'epoch' + %f * INTERVAL '1 second')" % time.mktime(when.timetuple())
        elif connection.vendor == "sqlite":
            return "DATETIME(%i.%i, 'unixepoch', 'localtime')" % (time.mktime(when.timetuple()), getattr(when, 'microsecond', 0))
        else:
            return '%s' % time.strftime("%Y-%m-%d %H:%M:%S", when.timetuple())

    def quote_string(self, data):
        data = str(data)
        data = data.replace('\\', '\\\\')
        data = data.replace('"', '\\"')
        data = data.replace("'", "\\'")
        data = data.replace('%', '%%')
        return "'" + str(data) + "'"

    def serialize(self, data):
        if isinstance(data, Decimal):
            if data.is_nan():
                return "0"
            return str(data)
        elif isinstance(data, float):
            if math.isnan(data):
                return "0"
            return str(data)
        elif isinstance(data, int):
            return str(data)
        elif type(data) in (datetime.datetime, datetime.date):
            return self.serialize_datetime(data)
        else:
            return self.quote_string(data)

    def sql(self):
        sql = "SELECT"
        if self.distinct:
            sql += " DISTINCT"
        if len(self.returns) > 0:
            sql += " " + ",".join(self.returns)
        else:
            sql += " *"
        sql += " FROM %s" % self.model._meta.db_table
        for j in self.joins:
            sql += " %s %s AS %s ON (%s)" % (
                j.get('jointype', 'LEFT OUTER JOIN'),
                j['model']._meta.db_table,
                j.get('joinas', j['model']._meta.db_table),
                " AND ".join(j['joinon']),
            )
        if len(self.where) > 0:
            sql += " WHERE " + " AND ".join(self.where)
        if len(self.groupby) > 0:
            sql += " GROUP BY " + ",".join(self.groupby)
        if len(self.having) > 0:
            sql += " HAVING " + " AND ".join(self.having)
        if self.sort:
            sort = []
            for s in self.sortlist():
                add = ''
                if s[0] == '-':
                    s = s[1:]
                    add =' DESC'
                elif s[0] == '+':
                    s = s[1:]
                    add = ' ASC'
                sort.append(s + add)
                if s in self.uniques:
                    break
            sql += " ORDER BY " + ",".join(sort)
        if self.limit:
            sql += " LIMIT %d" % self.limit
        if self.offset:
            sql += " OFFSET %d" % self.offset

        return sql + ";"
    def run(self):
        return self.model.objects.raw(self.sql())

    def run_raw(self):
        cursor = connection.cursor()
        cursor.execute(self.sql())
        return cursor.fetchone()


def _getFields(qset=None, model=None):
    """
    returns a list of fields for specified QuerySet or Model
    """
    if hasattr(qset, '_meta') and getattr(qset, '_meta') != None:
        fields = qset._meta.fields
    elif hasattr(qset, 'model') and getattr(qset, 'model') != None:
        fields = qset.model._meta.fields
    elif hasattr(qset, 'keys'):
        return list(qset.keys())
    elif hasattr(model, '_meta') and getattr(model, '_meta') != None:
        fields = model._meta.fields
    else:
        return None
    if fields:
        return list(f.name for f in fields)
    return None


def _returnResults(request, ret, accept_list=None, status=200):
    """
    returns a response data object in json, text or html
    """
    # figure return type
    if not accept_list:
        if request and request.DATA.get('_type', None):
            accept_list = [request.DATA.get('_type')]
        elif request and 'HTTP_ACCEPT' in request.META:
            accept_list = request.META["HTTP_ACCEPT"].split(',')
        elif request and 'HTTP_ACCEPT_ENCODING' in request.META:
            accept_list = request.META["HTTP_ACCEPT_ENCODING"].split(',')
        else:
            accept_list = []

    for i in range(len(accept_list)):
        a2 = accept_list[i].split(";", 1)
        if len(a2) == 2:
            accept_list[i] = a2[0]

    if "data" not in accept_list:
        ret["datetime"] = time.time()
        if "status" not in ret:
            ret["status"] = True

    # render response
    if 'data' not in accept_list and hasattr(settings, "DEBUG_REST_OUTPUT") and settings.DEBUG_REST_OUTPUT:
        if hasattr(settings, "DEBUG_REST_END_POINTS") and settings.DEBUG_REST_END_POINTS:
            for ep in settings.DEBUG_REST_END_POINTS:
                if request.path.startswith(ep):
                    PersistentLog.log(ret, 0, request, "rest", action="response")
                    break
        else:
            PersistentLog.log(ret, 0, request, "rest", action="response")

    if 'application/json' in accept_list:
        callback = request.DATA.get('callback', None)
        if callback:
            return HttpResponse("%s(%s)" % (callback, toJSON(ret)), content_type="application/json", status=status)
        try:
            return HttpResponse(toJSON(ret), content_type="application/json", status=status)
        except Exception as err:
            helpers.log_print(ret)
            raise err
    elif 'text/html' in accept_list:
        output = prettyJSON(ret)
        req_dict = request.DATA.asDict()
        req_out = prettyJSON(req_dict)
        # output = json.dumps(ret, sort_keys=True, indent=4, separators=(',', ': '), cls=JSONEncoderExt)
        # req_out = json.dumps(request.DATA.asDict(), sort_keys=True, indent=4, separators=(',', ': '), cls=JSONEncoderExt)

        # req_out = pprint.pformat(request.DATA.asDict(), indent=4).strip()
        path = request.path
        parts = path.split('/')
        last_pk = parts.pop()
        if last_pk and last_pk.isdigit():
            path = "/".join(parts)
        else:
            last_pk = ""

        is_debug = getattr(settings, "DEBUG", False) or getattr(settings, "REST_DEBUGGER", False)
        rest_help = {}
        if is_debug and hasattr(request, "rest_class"):
            rest_help = request.rest_class.get_rest_help()
            rest_help = prettyJSON(rest_help)
        context = {
            "help": rest_help,
            "input": req_dict,
            "pk": last_pk,
            "output_dict": ret,
            "output": output,
            "req_out":req_out,
            "path":path,
            "method": request.method,
            "debug":is_debug,
            "request": request,
            "version": VERSION
        }
        return render(request, "rest_html.html", context, status=status)
    elif 'text/plain' in accept_list:
        return HttpResponse(pprint.pformat(ret), content_type="text/plain", status=status)
    elif 'data' in accept_list:
        return ret
    else:
        return HttpResponse(toJSON(ret), content_type="text/plain", status=status)

def _filter_recurse(remove, lst):
    if isinstance(lst, dict):
        ret = {}
    else:
        ret = []
    for item in lst:
        if isinstance(lst, dict):
            if item[:len(remove)+1] == remove + ".":
                ret[item[len(remove)+1:]] = lst[item]
        elif type(item) in (list,tuple) and type(item[0]) in (str, str):
            p = item[0]
            if p[:len(remove)+1] == remove + ".":
                ret.append((p[len(remove)+1:], item[1]))
        elif type(item) in (str, str):
            if item[:len(remove)+1] == remove + ".":
                ret.append(item[len(remove)+1:])

    return ret

def restReturn(request, data, accept_list=None):
    return _returnResults(request, data, accept_list)

def __call_func(func, *args, **kwargs):
    if not kwargs:
        return func(*args)
    take = inspect.getargspec(func)[0]
    give = {}
    for arg in kwargs:
        if arg in take:
            give[arg] = kwargs[arg]
    return func(*args, **give)

def rest_serialize(data):
    if isinstance(data, datetime.datetime):
        try:
            return time.mktime(data.timetuple())
        except:
            print(("invalid date: {0}".format(data)))
        return 0.0
    elif isinstance(data, datetime.date):
        return data.strftime("%Y/%m/%d")
    elif isinstance(data, dict):
        data = data.copy()
        for k in list(data.keys()):
            data[k] = rest_serialize(data[k])
    elif isinstance(data, list) or isinstance(data, tuple):
        newdata = []
        for v in data:
            newdata.append(rest_serialize(v))
        data = newdata
    elif isinstance(data, float):
        if math.isnan(data):
            return 0.0
    elif isinstance(data, Decimal):
        if data.is_nan():
            return 0.0
        return float(data)
    return data

def updateFeature(func, request, qset, featuresets={}, features=[], **kwargs):
    features = list(features)
    kwargs = kwargs.copy()
    if not featuresets:
        return None

    got_features = []
    for f in getattr(request, 'REQUEST', {}).get('features', '').split(','):
        fs = f.strip()
        if fs != '':
            features.append(fs)

    agent = getattr(request, 'META', {}).get('HTTP_USER_AGENT', '')
    for a in getattr(settings, 'REST_USERAGENT_FEATURES', []):
        if re.match(a[0], agent):
            for f in a[1]:
                features.append(f)

    for f in features:
        if f in got_features:
            continue
        if f in featuresets and not f in got_features:
            got_features.append(f)
            for p,v in list(featuresets[f].items()):
                p_type = 'A'
                if p[:4] == 'DEL_':
                    p_type = 'D'
                    p = p[4:]
                elif p[:4] == 'ADD_':
                    p_type = 'A'
                    p = p[4:]
                elif p[:8] == 'REPLACE_':
                    p_type = 'R'
                    p = p[8:]

                if p_type == 'A' and p == 'features':
                    for ff in v:
                        features.append(ff)
                    continue

                if not p in kwargs:
                    raise ValueError('Invalid feature key: %s' % p)

                if p_type == 'R':
                    kwargs[p] = copy.deepcopy(v)
                    continue

                if type(kwargs[p]) == tuple:
                    kwargs[p] = list(kwargs[p])
                else:
                    kwargs[p] = copy.deepcopy(kwargs[p])

                if p_type == 'D' and hasattr(kwargs[p], 'remove'):
                    for i in v:
                        try:
                            kwargs[p].remove(i)
                        except ValueError:
                            pass
                elif p_type == 'D' and hasattr(kwargs[p], '__delitem__'):
                    for i in v:
                        try:
                            del(kwargs[p][i])
                        except KeyError:
                            pass
                elif p_type == 'A' and hasattr(kwargs[p], 'append'):
                    for i in v:
                        if not i in kwargs[p]:
                            kwargs[p].append(i)
                elif p_type == 'A' and hasattr(kwargs[p], '__setitem__'):
                    for i in v:
                        kwargs[p][i] = v[i]
                else:
                    raise ValueError('Invalid feature action: %s' % p)

    if got_features:
        return func(request, qset, features=features, **kwargs)
    else:
        return None

def restGet(request, qset, model=None, fields=None, extra=[], exclude=[], fkey_depth=0, recurse_into=[], filter={}, orig_request=None, orig_objs={}, ignore_noattr=False, require_perms=[], accept_list=None, featuresets={}, features=[], return_httpresponse=True):
    """
    request: HttpRequest object
    qset: QuerySet or data object to return
    model: (optional) model of the queryset
    fields: (optional) fields to return, default to all fields.  string, or tuple(db_field, output_field)
    extra: (optional) extra fields to return
    exclude: (optional) do not display these fields
    fkey_depth: (optional) levels to recurse into foreign keys, default 0
    recurse_into: (optional) list of foreign keys in data that should be recursed into, regardless of fkey_depth
    filter: (optional) filters for recurse fetch (default all)
    ignore_noattr: (optional) ignore unknown attributes (default false)
    accept_list: (optional) requested return format
    RETURN: HttpResponse

    process a RESTful GET request to get an object.  User is responsible for checking permissions, etc before calling.
    """
    # if not request:
    #   request = get_request()

    ret = updateFeature(restGet, request, qset, model=model, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, orig_request=orig_request, orig_objs=orig_objs, ignore_noattr=ignore_noattr, require_perms=require_perms, accept_list=accept_list, featuresets=featuresets, features=features)
    if ret != None:
        return ret

    for p in require_perms:
        if not (request.user and request.user.has_perm(p)):
            return _returnResults(request, {'status': False, 'error': 'Permission denied'}, accept_list=accept_list)

    if not orig_request:
        orig_request=request
    ret = {}

    # if no qset then 404
    if not qset:
        raise Http404
    if type(qset) == QuerySet:
        try:
            qset = qset[0]
        except IndexError:
            raise Http404

    if not fields or list(fields) == ["*"]:
        fields = _getFields(qset, model)
        #print fields
    if not model:
        model = getattr(qset, "__class__", None)

    if request and model:
        if hasattr(model, "on_rest_request") and not hasattr(request, "rest_class"):
            request.rest_class = model

    objs = orig_objs.copy()
    objs['obj__parent'] = qset
    if model and hasattr(model, '__name__'):
        objs['obj_' + model.__name__] = qset

    if "*" in exclude:
        fields = []

    for f in extra:
        if f[:2] == "*.":
            f = f[2:]
        if "." in f:
            continue
        if not f in fields:
            fields.append(f)
    # helpers.log_print("fields: {}".format(fields))
    recursed = []
    # get fields into data object, recurse if necessary
    for f in fields:
        if type(f) in (list, tuple):
            fout = f[1]
            f = f[0]
        else:
            fout = f

        fargs = []
        if type(f) is str and "|" in f:
            fargs = f.split("|")
            f = fargs.pop(0)
        if type(f) in (types.FunctionType, types.LambdaType):
            data = f(qset)
        elif f in exclude or "*."+f in exclude:
            continue
        elif f[0] == "!":
            f = f[1:]
            if fout[0] == "!":
                fout = fout[1:]
            data = qset
            for s in f.split("."):
                data = getattr(data, s)
                if data == None:
                    break
                if hasattr(data, '__func__'):
                    data = __call_func(data, request = orig_request, obj__self=qset, **orig_objs)
        else:
            if "." in f:
                continue
            try:
                # exc_info = sys.exc_info()
                # traceback.print_stack()
                data = getattr(qset, f)
            except AttributeError as err:
                try:
                    data = qset[f]
                except (TypeError, KeyError, IndexError):
                    if ignore_noattr:
                        continue
                    else:
                        # traceback.print_stack()
                        # traceback.print_exception(*exc_info)
                        # print str(traceback.format_exc())
                        helpers.log_print("{} has no attribute: {}".format(type(qset), f), fields)
                        # helpers.log_exception(err)
                        continue
        if isinstance(data, dict) and hasattr(data, "asDict"):
            data = data.asDict()
        elif hasattr(data, '__func__'):
            # helpers.log_print("__func__  {} ({}) {}".format(f, type(data), data))
            data = __call_func(data, *fargs, request = orig_request, obj__self=qset, **orig_objs)
        elif f.startswith("get_") and f.endswith("_display") and callable(data):
            data = data()

        # helpers.log_print("{} ({}) {}".format(f, type(data), data))
        data = rest_serialize(data)
        # print("{} ({}) {}".format(f, type(data), data))
        if isinstance(data, models.Model):
            if f in recurse_into:
                pass
            elif fkey_depth > 0:
                recurse_into.append((f, fout))
            elif hasattr(qset, f + "_id"):
                ret[fout] = getattr(qset, f + "_id")
            else:
                ret[fout] = data.pk
        elif hasattr(data, 'all'):
            if f in recurse_into:
                pass
            elif fkey_depth > 0:
                recurse_into.append((f, fout))
        else:
            ret[fout] = data


    # helpers.log_print("fields", fields)
    # helpers.log_print("recurse_into", recurse_into)

    for f in recurse_into:
        # print "-"*30
        # print recurse_into
        if '.' in f: continue
        if type(f) in (list, tuple):
            fout = f[1]
            f = f[0]
        else:
            fout = f
        fname = fout
        if fname == "":
            fname = f
        if f[:2] == "*.":
            f = f[2:]
        if fname in recursed:
            continue
        recursed.append(fname)
        rset = None
        odata = {}
        has_field = hasattr(qset, f)

        if f.startswith("generic__") and hasattr(qset, "restGetGenericRelation"):
            # print "handling generic: " + f
            # our generic relationship parser
            generic_graph = "generic"
            if fout != f:
                generic_graph = fout
            fout = f.split("__")[1]
            try:
                obj = qset.restGetGenericRelation(fout)
            except Exception as err:
                helpers.log_print("generic relationship error")
                helpers.log_exception(err)
                obj = None
            if not obj:
                continue
            # print ret
            odata = restGet(request, obj, accept_list=['data'], orig_request=orig_request, **obj.getGraph(generic_graph))
            odata["model"] = getattr(qset, fout)
            gkey = "{0}_id".format(fout)
            if gkey in ret:
                del ret[gkey]
        elif has_field and (hasattr(getattr(qset, f), 'all') or isinstance(getattr(qset, f), list)):
            rset = getattr(qset, f)
            odata = []
        elif isinstance(qset, dict) and f in qset and (hasattr(qset.get(f), 'all') or isinstance(qset.get(f), list)):
            rset = qset[f]
            odata = []
        elif hasattr(qset, f + '_set'):
            rset = getattr(qset, f + '_set')
            odata = []
        elif has_field and isinstance(getattr(qset, f), models.Model):
            odata = restGet(request, getattr(qset, f), fields=_filter_recurse(fname, fields), extra=_filter_recurse(fname, extra), exclude=_filter_recurse(fname, exclude), fkey_depth=fkey_depth-1, recurse_into=_filter_recurse(fname, recurse_into), filter=_filter_recurse(fname, filter), accept_list=['data'], orig_request=orig_request, orig_objs=objs)
        elif isinstance(qset, dict) and f in qset and isinstance(qset.get(f), models.Model):
            odata = restGet(request, qset.get(f), fields=_filter_recurse(fname, fields), extra=_filter_recurse(fname, extra), exclude=_filter_recurse(fname, exclude), fkey_depth=fkey_depth-1, recurse_into=_filter_recurse(fname, recurse_into), filter=_filter_recurse(fname, filter), accept_list=['data'], orig_request=orig_request, orig_objs=objs)
        elif isinstance(qset, dict) and f in qset and isinstance(qset.get(f), dict):
            odata = qset.get(f)
        elif has_field and callable(getattr(qset, f)):
            rset = getattr(qset, f)()
            if rset is not None:
                odata = []
        # elif has_field and hasattr(getattr(qset, f), 'im_func'):
        #     rset = getattr(qset, f)()
        #     if rset is not None:
        #         odata = []
        elif isinstance(qset, dict) and f in qset and callable((qset.get(f))):
            rset = qset.get(f)()
            odata = []
        else:
            odata = {}
        if rset and isinstance(rset, models.Model):
            odata = restGet(request, rset, fields=_filter_recurse(fname, fields), extra=_filter_recurse(fname, extra), exclude=_filter_recurse(fname, exclude), fkey_depth=fkey_depth-1, recurse_into=_filter_recurse(fname, recurse_into), filter=_filter_recurse(fname, filter), accept_list=['data'], orig_request=orig_request, orig_objs=objs)
            rset = None
        if rset:
            filt = filter.get(fname, None)
            if isinstance(rset, list):
                pass
            elif filt:
                rset = rset.filter(**filt)
            elif hasattr(rset, "all"):
                rset = rset.all()

            if type(rset) is list and len(rset) and not hasattr(rset[0], "id"):
                odata = rset
            elif isinstance(rset, dict) or type(rset) in [float, int, str]:
                odata = rset
            else:
                # print "-" * 80
                # print fname
                # print fields
                odata = restListEx(None, rset, size=0, fields=_filter_recurse(fname, fields), extra=_filter_recurse(fname, extra), exclude=_filter_recurse(fname, exclude), fkey_depth=fkey_depth-1, recurse_into=_filter_recurse(fname, recurse_into), filter=_filter_recurse(fname, filter), accept_list=['data'], orig_request=orig_request, orig_objs=objs)

        if fout:
            #print "1: {0} = {1}".format(fout, odata);
            if isinstance(odata, dict) and len(odata) == 0:
                odata = None
            ret[fout] = odata
        else:
            # print "2: {0} = {1}".format(fout, odata);
            if type(odata) == list:
                if len(odata[:1]) == 0:
                    continue
                odata = odata[0]
            for x in odata:
                # never allow overriding id for emptry recurse
                if x == "id":
                    continue
                ret[x] = odata[x]

    if return_httpresponse:
        if not (accept_list != None and 'data' in accept_list):
            ret = { 'status': True, 'data': ret }
        return _returnResults(request, ret, accept_list)

    return ret

def _order_list(ordering, data, dir, clear=False):
    ret = {"_dir": dir}
    if dir == '=':
        for r in data:
            ret[r] = data[r]
    else:
        for (o, rev) in ordering:
            try:
                name = o.attname
            except AttributeError:
                name = o.split(".")[-1]
            r = getattr(data, name)
            if type(r) in (datetime.datetime, datetime.date):
                r = {"datetime": [int(time.mktime(r.timetuple())), getattr(r, 'microsecond', 0)]}
            ret[getattr(o, 'name', o)] = r
    ret = toJSON(ret);
    if not clear:
        ret = base64.b64encode(ret.encode("utf-8")).decode("utf-8")
    return ret


def restListOther(request, qset, size=25, start=0, sort=None, accept_list=None, return_httpresponse=True):

    if request:
        sort = request.DATA.get("sort", sort)
        size = request.DATA.get(['size', '_size'], size, field_type=int)
        start = request.DATA.get(['start', '_start'], start, field_type=int)

    # if sort and sort.lstrip('-') in fields:
    #   sort = rsort

    if sort:
        reversed = sort[0] == '-'
        prop = sort
        if reversed:
            prop = sort.lstrip('-')

        qset.sort(key=lambda props: getattr(props, prop), reverse=reversed)

    data_list = []
    for obj in qset:
        if type(obj) in [float, int, str, Decimal]:
            data_list.append(obj)
        elif isinstance(obj, dict):
            data_list.append(rest_serialize(obj))
        elif hasattr(obj, "restGet"):
            data_list.append(obj.restGet(request, as_dict=True))
        else:
            helpers.log_print("unhandled type: {}: '{}'".format(type(obj), obj))

    if not return_httpresponse:
        return data_list
    count = len(data_list)
    data_list = data_list[:size]
    # build response
    ret = {}
    ret["size"] = size
    ret["count"] = count
    ret["start"] = start
    ret["data"] = data_list
    return _returnResults(request, ret, accept_list)


def restList(request, qset, model=None, size=25, start=0, sort=None, fields=None, extra=[], exclude=[], fkey_depth=0, recurse_into=[], filter={}, get_count=True, orig_request=None, orig_objs={}, page=None, ignore_noattr=False, todata=lambda x: x, require_perms=[], accept_list=None, featuresets={}, features=[], return_httpresponse=True, totals=None):
    """
    request: HttpRequest object
    qset: QuerySet or data object to return
    model: (optional) model of the queryset
    size: (optional) return set size, default 25, can override via GET[size].  0=return all.
    start: (optional) return set offset, default 0, can override via GET[start]
    sort: (optional) return set sorting, default None, can override via GET[sort]
    fields: (optional) fields to return, default to all fields
    extra: (optional) extra fields to return
    exclude: (optional) do not display these fields
    fkey_depth: (optional) levels to recurse into foreign keys, default 0
    recurse_into: (optional) list of foreign keys in data that should be recursed into, regardless of fkey_depth
    filter: (optional) filters for recurse fetch (default all)
    get_count: (optional) boolean of whether to get a count of total records available
    page: (optional) pagination token, can override via GET[page]
    ignore_noattr: (optional) ignore unknown attributes (default false)
    todata: (optional) function to convert per-element data into data for restGet
    accept_list: (optional) requested return format
    RETURN: HttpResponse

    process a RESTful GET request to list a set of objects.  User is responsible for checking permissions, etc before calling.
    """
    ffunc = updateFeature(restList, request, qset, model=model, size=size, start=start, sort=sort, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, get_count=get_count, orig_request=orig_request, orig_objs=orig_objs, page=page, ignore_noattr=ignore_noattr, todata=todata, require_perms=require_perms, accept_list=accept_list, featuresets=featuresets, features=features)
    if ffunc != None:
        return ffunc

    if type(qset) in [list, tuple]:
        return restListOther(request, qset, size, start, sort, accept_list, return_httpresponse)
    elif type(qset) != QuerySet:
        raise Exception("qset of type '{}' not supported for restList".format(type(qset)))

    if not model:
        model = getattr(qset, "model", None)

    if not fields:
        fields = _getFields(qset, model)

    if request:
        # values from request
        size = request.DATA.get(['size', '_size'], size, field_type=int)
        start = request.DATA.get(['start', '_start'], start, field_type=int)
        sort = request.DATA.get('sort', sort)

    count = 0
    if get_count:
        count = qset.count()

    if sort and isinstance(sort, str):
        if "metadata" in sort:
            sort = ""
        elif sort.endswith("_display"):
            # fix for django _display kinds being sorted
            sort = sort[:sort.find("_display")]
    # handle sorting
    sort_args = None
    if sort and type(qset) == QuerySet:
        sort_args = []
        for s in sort.split(","):
            s = s.replace('.', '__')
            sort_args.append(s)

        if sort_args:
            try:
                qset = qset.order_by(*sort_args)
            except Exception:
                helpers.log_exception("sorting error", sort_args)

    qset, ret = updatePagination(request, qset, size, count, start, page)

    qset = qset[:size]
    # print fields
    data_list = []
    for obj in qset:
        if type(obj) in [list, tuple, QuerySet]:
            data_list.append(restList(request, todata(obj), model=model, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, ignore_noattr=ignore_noattr, accept_list=['data'], orig_request=orig_request, orig_objs=orig_objs, return_httpresponse=False))
        else:
            data_list.append(restGet(request, todata(obj), model=model, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, ignore_noattr=ignore_noattr, accept_list=['data'], orig_request=orig_request, orig_objs=orig_objs))

    if not return_httpresponse:
        return data_list

    if totals:
        ret.update(totals)

    # build response
    ret["size"] = size
    ret["count"] = count
    ret["start"] = start
    ret["data"] = data_list
    if sort_args:
        ret["sort"] = sort_args
    return _returnResults(request, ret, accept_list)


def updatePagination(request, qset, size, count, start, page):
    # decode our page data object if it exists
    if not request:
        return qset, {}
    page = request.DATA.get('page', page)

    if page:
        page_data = json.loads(base64.b64decode(page))
    else:
        page_data = {'_dir': '!'}

    if page_data['_dir'] == '=':
        start = page_data.get('start', start)

    ordering = None
    if type(qset) == QuerySet and qset.query.can_filter():
        ordering = []
        if not qset.ordered:
            modelorder = []
        elif qset.query.extra_order_by:
            modelorder = qset.query.extra_order_by
        elif not qset.query.default_ordering:
            modelorder = qset.query.order_by
        else:
            modelorder = qset.query.order_by or qset.query.model._meta.ordering or []
        modelorder = list(modelorder)
        modelorder.append('pk')
        qset = qset.order_by(*modelorder)
        try:
            for o in qset.query.order_by:
                rev = False
                if o[0] == '-':
                    rev = True
                    o = o[1:]
                if o == 'pk':
                    o = qset.model._meta.pk
                else:
                    o = qset.model._meta.get_field(o) # raises FieldDoesNotExist
                ordering.append((o, rev))
                if o.unique:
                    break
        except FieldDoesNotExist:
            pass

    # parse supplied paging info
    do_reverse = False
    first_page = start == 0
    last_page = False
    if ordering:
        qfilter = None
        qfilter2 = {}
        rfilter = []
        rfilter2 = []
        for (o, rev) in ordering:
            name = getattr(o, 'name', o)
            if not name in page_data:
                continue
            # pull page data by name
            if isinstance(page_data[name], dict) and "datetime" in page_data[name]:
                data = datetime.datetime.fromtimestamp(page_data[name]["datetime"][0])
                data = data.replace(microsecond=page_data[name]["datetime"][1])
            elif isinstance(page_data[name], dict) and "date" in page_data[name]:
                data = datetime.date.fromtimestamp(page_data[name]["date"][0])
            else:
                data = page_data[name]

            if type(qset) == QuerySet:
                if rev == (page['_dir'] == '+'):
                    att = name + "__lt"
                else:
                    att = name + "__gt"

                qfilter3 = qfilter2.copy()
                qfilter3[att] = data
                if not qfilter:
                    qfilter = Q(**qfilter3)
                else:
                    qfilter = qfilter | Q(**qfilter3)

                if o.unique:
                    break

                qfilter2[o.name] = data

        if qfilter:
            qset = qset.filter(qfilter)
        if page_data['_dir'] == '-':
            do_reverse = True
        first_page = False

    # if do_reverse:
    #   if size:
    #       qset = qset.reverse()[:size+1]
    #   else:
    #       qset.reverse()

    if size:
        qset = qset[start:start+size+1]

    ret = {}
    ret["start"] = start

    if ordering:
        try:
            if not first_page:
                ret['page_prev'] = _order_list(ordering, qset[0], '-')
            else:
                ret['page_before'] = _order_list(ordering, qset[0], '-')
        except IndexError:
            pass
        try:
            if do_reverse:
                offset = -1
            else:
                offset = size-1
            if size > 0 and not last_page:
                ret['page_next'] = _order_list(ordering, qset[offset], '+')
            elif size > 0:
                ret['page_after'] = _order_list(ordering, qset[offset], '+')
        except IndexError:
            try:
                ret['page_after'] = _order_list(ordering, qset[-1], '+')
            except:
                pass

    return qset, ret

# def restListQuerySet(request, )

def restListEx(request, qset, model=None, size=25, start=0, sort=None, fields=None, extra=[], exclude=[], fkey_depth=0, recurse_into=[], filter={}, get_count=True, orig_request=None, orig_objs={}, page=None, ignore_noattr=False, todata=lambda x: x, require_perms=[], accept_list=None, featuresets={}, features=[], return_httpresponse=True):
    """
    request: HttpRequest object
    qset: QuerySet or data object to return
    model: (optional) model of the queryset
    size: (optional) return set size, default 25, can override via GET[size].  0=return all.
    start: (optional) return set offset, default 0, can override via GET[start]
    sort: (optional) return set sorting, default None, can override via GET[sort]
    fields: (optional) fields to return, default to all fields
    extra: (optional) extra fields to return
    exclude: (optional) do not display these fields
    fkey_depth: (optional) levels to recurse into foreign keys, default 0
    recurse_into: (optional) list of foreign keys in data that should be recursed into, regardless of fkey_depth
    filter: (optional) filters for recurse fetch (default all)
    get_count: (optional) boolean of whether to get a count of total records available
    page: (optional) pagination token, can override via GET[page]
    ignore_noattr: (optional) ignore unknown attributes (default false)
    todata: (optional) function to convert per-element data into data for restGet
    accept_list: (optional) requested return format
    RETURN: HttpResponse

    process a RESTful GET request to list a set of objects.  User is responsible for checking permissions, etc before calling.
    """
    start_time = time.time()
    ret = updateFeature(restList, request, qset, model=model, size=size, start=start, sort=sort, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, get_count=get_count, orig_request=orig_request, orig_objs=orig_objs, page=page, ignore_noattr=ignore_noattr, todata=todata, require_perms=require_perms, accept_list=accept_list, featuresets=featuresets, features=features)
    # print "s1 {}".format(time.time() - start_time)
    # print "!! warning calling depercated restListEx"
    if ret != None:
        return ret

    for p in require_perms:
        if not (request.user and request.user.has_perm(p)):
            return _returnResults(request, {'status': False, 'error': 'Permission denied'}, accept_list=accept_list)

    # print "s2 {}".format(time.time() - start_time)
    if not orig_request:
        orig_request=request
    ret = {}
    rsort = sort
    t3 = time.time()
    if not fields:
        fields = _getFields(qset, model)
    # print "\tt3 {}".format(time.time() - t3)
    if not model:
        model = getattr(qset, "model", None)
    # print "\tt3 {}".format(time.time() - t3)
    # get overrides via HTTP
    if request:
        try:
            if size == '*':
                size = 0
            else:
                size = int(request.DATA.get('size', size))
        except ValueError:
            pass
        try:
            if start == '*':
                start = 0
            else:
                start = int(request.DATA.get(['start', '_start'], start))
        except ValueError:
            pass
        if sort == '*':
            sort = None
            rsort = None
        else:
            rsort = request.DATA.get('sort', sort)

        if get_count:
            if type(get_count) == int:
                ret['count'] = get_count
            elif type(qset) in (list, tuple):
                ret['count'] = len(qset)
            elif qset == None:
                ret['count'] = 0
            elif hasattr(qset, "count"):
                t4 = time.time()
                # # print qset.query
                ret['count'] = qset.count()
                # print "\tt4 {}".format(time.time() - t4)
        page = request.DATA.get('page', page)
    # print "s3 {}".format(time.time() - start_time)
    try:
        page = json.loads(base64.b64decode(page))
        if not page.get('_dir') in ('+', '-', '='):
            raise ValueError
    except (ValueError, TypeError):
        page = {'_dir': '!'}

    if page['_dir'] == '=':
        start = page.get('start', start)

    ret['start'] = start
    ret['size'] = size

    if isinstance(rsort, str):
        if "metadata." in rsort:
            rsort = ""
    # do sorting
    if rsort:
        if type(qset) == RawQuery:
            if re.match("[+-]?[a-zA-Z0-9._,]+", rsort):
                qset.sort = rsort.split(",")
        elif not type(qset) in (list, tuple):
            sort = []
            # for s in str(rsort).split(","):
            #   if s.lstrip('-') in  (type(x) in (list,tuple) and x[0] or x for x in list(fields) + list(recurse_into)):
            #       sort.append(s.replace('.', '__'))
            for s in str(rsort).split(","):
                s = s.replace('.', '__')
                sort.append(s)

            if sort:
                qset = qset.order_by(*sort)
                ret['sort'] = sort
        elif type(qset) == list:
            if rsort and rsort.lstrip('-') in fields:
                sort = rsort

            if sort:
                reversed = rsort[0] == '-'
                prop = rsort
                if reversed:
                    prop = rsort.lstrip('-')

                qset.sort(key=lambda props: getattr(props, prop), reverse=reversed)
    # print "s4 {}".format(time.time() - start_time)
    # sane paging - get ordering list
    ordering = []
    try:
        if type(qset) == QuerySet and qset.query.can_filter():
            if not qset.ordered:
                modelorder = []
            elif qset.query.extra_order_by:
                modelorder = qset.query.extra_order_by
            elif not qset.query.default_ordering:
                modelorder = qset.query.order_by
            else:
                modelorder = qset.query.order_by or qset.query.model._meta.ordering or []
            modelorder = list(modelorder)
            modelorder.append('pk')
            qset = qset.order_by(*modelorder)
            for o in qset.query.order_by:
                rev = False
                if o[0] == '-':
                    rev = True
                    o = o[1:]
                if o == 'pk':
                    o = qset.model._meta.pk
                else:
                    o = qset.model._meta.get_field(o) # raises FieldDoesNotExist
                ordering.append((o, rev))
                if o.unique:
                    break
        elif type(qset) == RawQuery:
            for o in qset.sortlist():
                rev = False
                if o[0] == '-':
                    rev = True
                    o = o[1:]
                ordering.append((o, rev))
                if o in qset.uniques:
                    break
    except FieldDoesNotExist:
        ordering = None
        pass
    # print "s5 {}".format(time.time() - start_time)
    # parse supplied paging info
    do_reverse = False
    first_page = start == 0
    last_page = False
    if ordering and request:
        try:
            try:
                page = json.loads(base64.b64decode(request.DATA.get('page', page)))
                if not page.get('_dir') in ('+', '-'):
                    raise FieldDoesNotExist
            except (ValueError, TypeError):
                raise FieldDoesNotExist

            qfilter = None
            qfilter2 = {}
            rfilter = []
            rfilter2 = []
            for (o, rev) in ordering:
                name = getattr(o, 'name', o)

                if not name in page:
                    raise FieldDoesNotExist

                if isinstance(page[name], dict) and "datetime" in page[name]:
                    data = datetime.datetime.fromtimestamp(page[name]["datetime"][0])
                    data = data.replace(microsecond=page[name]["datetime"][1])
                elif isinstance(page[name], dict) and "date" in page[name]:
                    data = datetime.date.fromtimestamp(page[name]["date"][0])
                else:
                    data = page[name]

                if type(qset) == QuerySet:
                    if rev == (page['_dir'] == '+'):
                        att = name + "__lt"
                    else:
                        att = name + "__gt"

                    qfilter3 = qfilter2.copy()
                    qfilter3[att] = data
                    if not qfilter:
                        qfilter = Q(**qfilter3)
                    else:
                        qfilter = qfilter | Q(**qfilter3)

                    if o.unique:
                        break
                    qfilter2[o.name] = data
                elif type(qset) == RawQuery:
                    if rev == (page['_dir'] == '+'):
                        att = name + "<"
                    else:
                        att = name + ">"

                    data = qset.serialize(data)
                    rfilter3 = list(rfilter2) + [att + data]
                    rfilter.append("(" + ") AND (".join(rfilter3) + ")")

                    if name in qset.uniques:
                        break
                    rfilter2.append(name + "=" + data)

            if type(qset) == QuerySet:
                qset = qset.filter(qfilter)
            elif type(qset) == RawQuery:
                qset.addWhere("((" + ") OR (".join(rfilter) + "))")
            if page['_dir'] == '-':
                do_reverse = True
            del ret['start']
            first_page = False
        except FieldDoesNotExist:
            pass
    # print "s6 {}".format(time.time() - start_time)
    if do_reverse:
        if type(qset) == QuerySet:
            if size:
                qset = list(qset.reverse()[:size+1])
                if len(qset) < size+1:
                    first_page = True
                else:
                    qset = qset[1:]
            qset.reverse()
        elif type(qset) == RawQuery:
            qset.reverse()
    # print "s7 {}".format(time.time() - start_time)
    if type(qset) == RawQuery:
        qset.offset = start
        if size:
            qset.limit = size+1
    elif size and qset != None:
        if do_reverse:
            qset = qset[start:start+size]
        else:
            t8 = time.time()
            # qset = list(qset[start:start+size+1])
            qset = qset[start:start+size+1]

            if qset.count() <= size:
                last_page = True
            else:
                qset = qset[:size]
            # print "t8 {}".format(time.time() - t8)
    # print "s8 {}".format(time.time() - start_time)
    if type(qset) == RawQuery:
        qset = list(qset.run())
        if do_reverse:
            if size:
                if qset.count() <= size:
                    first_page = True
                else:
                    qset = qset[:-1]
            qset.reverse()
        elif size:
            if qset.count() <= size:
                last_page = True
            else:
                qset = qset[:-1]
    # print "s9 {}".format(time.time() - start_time)
    # get list of data
    if "key" in extra and "value" in extra and len(extra) == 2 and "*" in exclude:
        ret['data'] = {}
        for qr in qset:
            qr = todata(qr)
            if hasattr(qr.key, '__func__'):
                key = qr.key()
            else:
                key = qr.key
            if hasattr(qr.value, '__func__'):
                value = qr.value()
            else:
                value = qr.value
            ret['data'][key] = rest_serialize(value)
    else:
        ret['data'] = []
        if qset:
            # # print fields
            for qr in qset:
                if type(qr) in [float, int, int, str, Decimal]:
                    ret['data'].append(qr)
                else:
                    # FIXME... wrong graph data????
                    ret['data'].append(restGet(request, todata(qr), model=model, fields=fields, extra=extra, exclude=exclude, fkey_depth=fkey_depth, recurse_into=recurse_into, filter=filter, ignore_noattr=ignore_noattr, accept_list=['data'], orig_request=orig_request, orig_objs=orig_objs))
    # print "s10 {}".format(time.time() - start_time)
    if accept_list and 'data' in accept_list:
        return _returnResults(request, ret['data'], accept_list)
    # print "s11 {}".format(time.time() - start_time)
    # fill in next/previous
    if ordering:
        try:
            if not first_page:
                ret['page_prev'] = _order_list(ordering, qset[0], '-')
            else:
                ret['page_before'] = _order_list(ordering, qset[0], '-')
        except IndexError:
            pass
        try:
            if do_reverse:
                offset = -1
            else:
                offset = size-1
            if size > 0 and not last_page:
                ret['page_next'] = _order_list(ordering, qset[offset], '+')
            elif size > 0:
                ret['page_after'] = _order_list(ordering, qset[offset], '+')
        except IndexError:
            try:
                ret['page_after'] = _order_list(ordering, qset[-1], '+')
            except:
                pass
    else:
        if not first_page:
            first = start - size
            if first < 0:
                first = 0
            ret['page_prev'] = _order_list(None, {'start': first}, '=')
        if size > 0 and not last_page and not ('count' in ret and start+size > ret['count']):
            ret['page_next'] = _order_list(None, {'start': start + size}, '=')
    # print "s12 {}".format(time.time() - start_time)
    if return_httpresponse:
        return _returnResults(request, ret, accept_list)
    return ret["data"]

def restSet(request, obj, initial=None, model=None, fields=None, form=None, data_override={}, retdata_func=None, retdata_args=[], return_object=False, accept_list=None, formopts={}, request_override={}):
    """
    request: HttpRequest object
    obj: Object to change
    initial: (optional) dictionary of default values, can be overwritten in http request
    model: (optional) model of the queryset
    fields: (optional) fields that can be set, default to all fields
    form: (optional) form used to validate change, defaults to no validation
    data_override: (optional) override object data after form processing
    retdata_func: (optional) function to return extra data (in dict form) for successful return status
    retdata_args: (optional) options to pass to retdata_func
    return_object: (optional, default False) return additional db object
    accept_list: (optional) requested return format
    RETURN: HttpResponse

    process a RESTful POST/PUT request to change an objects.  User is responsible for checking permissions, etc before calling.
    """
    # get valid fields from form
    if form:
        if not fields:
            fields = form.base_fields

    # filter input based on fields
    if not fields:
        fields = _getFields(obj, model)
        try:
            fields.remove('id')
        except ValueError:
            pass

    data = request.DATA

    # validate input
    if form:
        ldict = MultiValueDict({"__request": [request]})
        for v in request_override:
            ldict[v] = request_override[v]
        if obj:
            newform = form(instance=obj, initial=initial, **formopts)
            for f in newform.initial:
                if not (f in request.DATA or ('_clear_' + f) in request.DATA):
                    if isinstance(newform.initial[f], list):
                        ldict.setlist(f, newform.initial[f])
                    else:
                        ldict[f] = newform.initial[f]
        data = helpers.mergeDicts(ldict, request.POST, request.GET)

        if obj:
            form = form(data, files=request.FILES, instance=obj, initial=initial, **formopts)
        else:
            form = form(data, files=request.FILES, initial=initial, **formopts)
        if form.is_valid():
            if data_override:
                obj = form.save(commit=False)
            else:
                obj = form.save()
        else:
            errs = {}
            errs_all = ""
            for f in form.fields:
                if form[f].errors:
                    errs[f] = []
                    for e in form[f].errors:
                        errs[f].append(e)

            for e in form.non_field_errors():
                if not errs.get('', None):
                    errs[''] = []
                errs[''].append(e)
            for f in errs:
                errs_all += "%s: %s\n" % ( f, ", ".join(errs[f]) )

            ret = _returnResults(request, {'status': False, 'error': errs_all, 'errors': errs}, accept_list=accept_list)
            if return_object:
                return (ret, None,)
            else:
                return ret
    else:
        if not obj:
            obj = model()
            for f in initial:
                setattr(obj, f, initial[f])
        for f in fields:
            if f in request_override:
                setattr(obj, f, request_override[f])
            if f in data:
                setattr(obj, f, data[f])
        if not data_override:
            obj.save()

    # apply override
    if data_override:
        for k in data_override:
            setattr(obj, k, data_override[k])
        obj.save()
        if form:
            form.save_m2m()

    if hasattr(obj, 'pk'):
        retdata = {'status': True, 'id': obj.pk}
    else:
        retdata = {'status': True}
    if retdata_func:
        retdata['data'] = retdata_func(*retdata_args, obj=obj)
    ret = _returnResults(request, retdata, accept_list=accept_list)
    if return_object:
        return (ret, obj,)

    return ret

def restAdd(request, *args, **kwargs):
    """
    request: HttpRequest object
    other options: same as restSet

    RETURN: HttpResponse

    process a RESTful POST/PUT request to add an objects.  User is responsible for checking permissions, etc before calling.
    """
    return restSet(request, None, *args, **kwargs)

def restDelete(request, obj, accept_list=None):
    """
    request: HttpRequest object
    obj: Object to delete
    accept_list: (optional) requested return format
    RETURN: HttpResponse

    process a RESTful DELETE request to delete an objects.  User is responsible for checking permissions, etc before calling.
    """
    try:
        oldid = obj.pk
        obj.delete()
        return _returnResults(request, {'status': True, 'id': oldid}, accept_list=accept_list)
    except:
        return _returnResults(request, {'status': False, 'error': 'Cannot delete'}, accept_list=accept_list)

def restPermissionDenied(request, error="permission denied", error_code=403):
    return restStatus(request, False, error=error, error_code=error_code)

def restNotFound(request):
    return restStatus(request, False, error="not found", error_code=404)

def restOK(request):
    return restStatus(request, True)

def restError(request, error, error_code=None):
    return restStatus(request, False, error=error, error_code=error_code)

def restStatus(request, status, data={}, accept_list=None, **kwargs):
    """
    request: HttpRequest object
    status: return status value
    accept_list: (optional) requested return format
    data: any other values to be returned
    kwargs: any other values to be returned
    RETURN: HttpResponse

    return a status using REST framework
    """
    if type(data) in [str, str]:
        if not status:
            data = {"error": data}
        else:
            data = {"message": data}
    ret = data.copy()
    ret.update(kwargs)
    ret['status'] = status
    # if settings.DEBUG and "error" in kwargs:
    #   print "RPC ERROR: {0}".format(kwargs["error"])
    return _returnResults(request, ret, accept_list)

_chunk_badchars = ''.join(list(chr(x) for x in list(range(0, ord('0'))) + list(range(ord('9')+1, ord('A'))) + list(range(ord('Z')+1, ord('a'))) + list(range(ord('z')+1, 256)) ))

def chunkUploadedFile(request, session):
    if (request.user and request.user.is_authenticated):
        uid = str(request.user.pk)
    else:
        uid = 'X'

    session = str(session).translate(None, _chunk_badchars)

    datafile = os.path.join(CHUNKDIR, uid + '-' + session)

    f = open(datafile, "r")
    data = eval(f.read())
    f.close()

    f = open(data['path'], "r")

    return UploadedFile(file=f, name=data.get('name'), content_type=data.get('content_type'), size=data.get('size'))

def chunkUploadView(request):
    for k in request.DATA:
        if k[-5:] == '.path':
            vname = k[:-5]
            break
    else:
        raise ValueError('No file uploaded')

    if not os.path.isdir(CHUNKDIR):
        os.makedirs(CHUNKDIR);

    if (request.user and request.user.is_authenticated):
        uid = str(request.user.pk)
    else:
        uid = 'X'

    infile = request.DATA[vname + '.path']
    name = request.DATA.get(vname + '.name', 'noname')
    if not name:
        name = 'noname'
    size = int(request.DATA[vname + '.size'])
    content_type = request.DATA.get(vname + '.content_type')

    sid = str(os.path.basename(infile))
    sid = sid.translate(None, _chunk_badchars)

    datafile = os.path.join(CHUNKDIR, uid + '-' + sid)
    outfile = os.path.join(datafile + "_file" + os.path.splitext(name)[1])

    if os.path.isfile(datafile):
        raise ValueError("Session ID Conflict: %s" % sid)

    os.rename(infile, outfile)

    f = open(datafile + ".tmp", "w")
    f.write(repr({
        'name': name,
        'size': size,
        'content_type': content_type,
        'path': outfile,
        'created': datetime.datetime.now(),
    }))
    f.close()
    os.rename(datafile + ".tmp", datafile)

    return restStatus(request, True, {'session-id': sid, 'name': name, 'content_type': content_type, 'size': size})

def generateCSVOLD(qset, fields, name, output=None):
    import csv

    if not output:
        output = StringIO()

    csvwriter = csv.writer(output)
    csvwriter.writerow(fields)

    try:
        for row in qset.values_list(*fields):
            row = [str(x) for x in row]
            csvwriter.writerow(row)
    except Exception as err:
        helpers.log_exception(err)
    return output

def flattenObject(obj, field_names):
    NOT_FOUND = "-!@#$%^&*()-"

    row = []
    for f in field_names:
        d = getattr(obj, f, NOT_FOUND)
        if d != NOT_FOUND:
            if callable(d):
                d = d()
        elif "." in f:
            f1, f2 = f.split('.')
            d1 = getattr(obj, f1, None)
            if d1:
                if not hasattr(d1, f2):
                    if hasattr(d1, "first"):
                        d1 = d1.first()
                d = getattr(d1, f2, "")
                if callable(d):
                    d = d()
            else:
                d = ""
        elif "__" in f:
            f1, f2 = f.split('__')
            d1 = getattr(obj, f1, None)
            if d1:
                if not hasattr(d1, f2):
                    if hasattr(d1, "first"):
                        d1 = d1.first()
                d = getattr(d1, f2, "")
            else:
                d = ""
        else:
            d = "n/a"
        row.append(str(d))
    return row

def extractFieldNames(fields):
    header = []
    field_names = []
    for f in fields:
        if type(f) is tuple:
            r, f = f
            field_names.append(r)
        else:
            field_names.append(f)
        header.append(f)
    return header, field_names

def generateCSV(qset, fields, name, header_cols=None, values_list=False, output=None, stream=False):
    import csv

    a = UberDict()
    a.name = name
    a.file = StringIO()
    if output:
        a.file = output
    csvwriter = csv.writer(a.file)
    header, field_names = extractFieldNames(fields)
    if header_cols:
        header = header_cols
    csvwriter.writerow(header)
    if values_list:
        for row in qset.values_list(*field_names):
            row = [str(x) for x in row]
            csvwriter.writerow(row)
    else:
        for obj in qset:
            csvwriter.writerow(flattenObject(obj, field_names))
    if hasattr(a.file, "getvalue"):
        a.data = a.file.getvalue()
    a.mimetype = "text/csv"
    return a

def iterCsvObject(items, writer, header, field_names):
    yield writer.writerow(header)
    for item in items:
        yield writer.writerow(flattenObject(item, field_names))

def generateCSVStream(qset, fields, name):
    import csv
    # check if we support stream mode
    header, field_names = extractFieldNames(fields)
    # rows = qset.values_list(*fields)
    pseudo_buffer = EchoWriter()
    writer = csv.writer(pseudo_buffer)
    return StreamingHttpResponse(
        iterCsvObject(qset, writer, header, field_names))

class EchoWriter(object):
    """An object that implements just the write method of the file-like
    interface.
    """
    def writeline(self, value):
        return "{}\n".format(value)

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


def restFlat(request, qset, fields, name, size=10000, header_cols=None):
    return HttpResponse(prettyJSON(list(qset.values_list(*fields))), content_type="application/json", status=200)


def restCSV(request, qset, fields, name, size=10000, header_cols=None):
    if size > 1200 and qset.count() > 1200:
        # large data set lets stream
        qset = qset[:size]
        response = generateCSVStream(qset, fields, name)
        response['Cache-Control'] = 'no-cache'
        response['Content-Disposition'] = 'attachment; filename="{0}"'.format(name)
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{0}"'.format(name)
        qset = qset[:size]
        generateCSV(qset, fields, name, output=response, header_cols=header_cols)
    return response


def restJSON(request, qset, fields, name, size=10000):
    data = restList(None, qset, fields=fields, size=size, accept_list=["application/json"], return_httpresponse=False)
    response = HttpResponse(prettyJSON(data), content_type="application/json")
    response['Content-Disposition'] = 'attachment; filename="{0}"'.format(name)
    return response


from . import url_docs
def showDocs(request):
    from . import urls
    apis, graphs = url_docs.getRestApis(urls.urlpatterns)
    for api in apis:
        api["url"] = "rpc/{0}".format(api["url"])
    return render(request, "rest_docs.html", {"apis": apis, "graphs":graphs})


def csrf_failure(request, reason=""):
    return restStatus(request, False, error="csrf failure: {0}".format(reason))
