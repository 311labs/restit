import os
import json
import string
from datetime import datetime, date
from auditlog.models import PersistentLog
from rest import helpers as rest_helpers
from rest.uberdict import UberDict
from objict import objict
from rest.crypto.privpub import PrivatePublicEncryption
from django.http.request import QueryDict

from django.conf import settings

NOTFOUND = "311!@#$%^&*"
SAFE_ASCII = set(string.printable)
# load decrypter
DECRYPTER_KEY_FILE = os.path.join(os.path.dirname(settings.ROOT), "config", "decrypt_key.pem")
DECRYPTER = None
if not os.path.exists(DECRYPTER_KEY_FILE):
    print(("WARNING, failed to load decrypter!!! {}".format(DECRYPTER_KEY_FILE)))
    DECRYPTER_KEY_FILE  = os.path.join(os.path.dirname(os.path.dirname(settings.ROOT)), "config", "decrypt_key.pem")

if os.path.exists(DECRYPTER_KEY_FILE):
    DECRYPTER = PrivatePublicEncryption(private_key_file=DECRYPTER_KEY_FILE)


class RequestData(object):

    @staticmethod
    def upgradeRequest(request, data=None):
        if not hasattr(request, "DATA"):
            request.DATA = RequestData(request, data)
            request.DATA.parse()

    def __init__(self, request=None, data=None):
        self.__data = data
        self.is_logged = False
        self.request = request
        if not self.request:
            return
        self.request.is_sns = False
        self.parsePARAMS()
        self.request.is_json = self.isJSON()

    def parse(self):
        if self.request.is_json:
            self.parseJSON()
        else:
            self.__data = self.params
        if self.request.is_sns:
            self.parseSNS()
        if self.__data is None:
            self.__data = {}

    def decrypt(self, key="emsg", nkey=None):
        """
        decrypt any emsg data that may be in this returning the data
        nkey is the fallback unencrypted key to look for
        """
        edata = self.get(key, None)
        if edata is None:
            if nkey:
                return self.get(nkey, None)
            return None
        if not DECRYPTER:
            raise Exception("decryption key not loaded")
        data = DECRYPTER.decrypt(edata)
        try:
            if data and data.startswith('{') or data.startswith('['):
                # data = json.loads(data)
                return UberDict.fromJSON(data)
        except Exception:
            pass
        return data

    def parseSNS(self):
        self.request.sns_type = self.get("type")
        self.request.sns_subject = self.get("subject")
        self.request.sns_topic = self.get("topicarn")
        self.request.sns_id = self.get("messageid")
        self.request.sns_signature = self.get("signature")
        # this should just be notification type "Received"
        if self.request.sns_subject and "Email Receipt" in self.request.sns_subject:
            data = self.get("message")
            if data:
                try:
                    self.__data = self.normalizeData(json.loads(data))
                    self.request.sns_type = "email"
                except Exception as err:
                    print("sns msg error")
                    print(data)
        elif self.request.sns_type == "Notification":
            data = self.get("message")
            if data:
                try:
                    self.__data = self.normalizeData(json.loads(data))
                    self.request.sns_type = self.get("notificationtype", self.request.sns_type)
                except Exception as err:
                    print("sns msg error")
                    print(data)

    def parsePARAMS(self):
        if self.request.method == "POST":
            data = self.request.POST
        elif self.request.method == "GET":
            data = self.request.GET
        elif self.request.method == "DELETE":
            data = dict()
        elif self.request.method == "PUT":
            if self.request.content_type == "application/json":
                data =  UberDict.fromJSON(self.request.body, ignore_errors=True)
            else:
                if hasattr(self.request, '_post'):
                    del self.request._post
                    del self.request._files
                try:
                    self.request.method = "POST"
                    self.request._load_post_and_files()
                    self.request.method = "PUT"
                except AttributeError:
                    self.request.META['REQUEST_METHOD'] = 'POST'
                    self.request._load_post_and_files()
                    self.request.META['REQUEST_METHOD'] = 'PUT'
                data = self.request.POST
        else:
            data = dict()
        self.params = UberDict.fromdict(self.normalizeData(data))

    def parseJSON(self):
        try:
            self.__data = UberDict.fromJSON(self.request.body, ignore_errors=False)
            if isinstance(self.__data, list):
                self.__data = UberDict(data=self.__data)
            self.__data.update(self.params)
            # data = UberDict.fromdict(dict(self.params))
            # self.__data = self.normalizeData(json.loads(self.request.body), data)
        except Exception:
            rest_helpers.log_exception(
                "request error", "{} -> {} {}".format(self.request.ip, self.request.method, self.request.path),
                dict(self.request.META))
            rest_helpers.log_error("request body", self.request.body)
            self.request.is_json = False
            return

    def isJSON(self):
        if "HTTP_X_AMZ_SNS_MESSAGE_TYPE" in self.request.META:
            self.request.is_sns = True
            return True
        ct = self.request.META.get('CONTENT_TYPE')
        if self.request.method == "POST" and ct:
            return "json" in ct.lower()
        return False

    def getHeader(self, name):
        if type(name) is list:
            for n in name:
                v = self.getHeader(n)
                if v is not None:
                    return v
        # X-Gitlab-Token
        name = name.upper()
        for key in self.request.META:
            if key.upper() == name:
                return self.request.META.get(key)
        return None

    def remove(self, key, default=None):
        if type(key) is list:
            v = None
            for k in key:
                v = self.remove(k)
                if v:
                    return v
            return default

        data, pk = self.getDictAndKey(key)
        if data:
            value = data[pk]
            del data[pk]
            return value
        return default

    def getDictAndKey(self, key, data=None):
        """
        This will return the dict that holds the key.
        used when going into nested objects
        """
        if data is None:
            data = self.__data
            if not data:
                return None, None

        if "." in key:
            keys = key.split('.')
            obj = None
            pk = None
            for k in keys:
                if not data:
                    return None, None

                obj, pk = self.getDataAndKey(k, data)
                if obj is None:
                    return None, None

                data = obj.get(key)
            return obj, pk

        for k in data:
            if type(k) in [str, str] and k.lower() == key.lower():
                return data, k
        return None, None

    def getIgnore(self, key, data=None):
        if data is None:
            data = self.__data

        if data:
            for k in data:
                if type(k) in [str, str] and k.lower() == key.lower():
                    return data.get(k)
        return NOTFOUND

    def getNormal(self, key, data=None):
        if data is None:
            data = self.__data

        if key in data:
            return data.get(key)
        return NOTFOUND

    def lowerKeys(self):
        if self.__data:
            self.__data = rest_helpers.lowerKeys(self.__data)

    def removeUnderscores(self):
        if self.__data:
            self.__data = rest_helpers.removeUnderscoreKeys(self.__data)

    def has_key(self, key):
        if type(key) is list:
            for k in key:
                if k in self:
                    return True
            return False
        value = self.get(key, NOTFOUND)
        return value != NOTFOUND

    def __iter__(self):
        return self.__data.__iter__()

    def __getattr__(self, key):
        return self.get(key)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __contains__(self, key):
        value = self.get(key, NOTFOUND)
        return value != NOTFOUND

    def __unicode__(self):
        if self.__data:
            return str(self.__data)
        return ""

    def log(self, include_headers=True):
        if not self.is_logged:
            self.is_logged = True
            track = self.get("track", None)
            cardnumber = self.get(["cardnumber", "pan"], None)
            password = self.get("password", None)
            sanitized = UberDict.fromdict(self.toDict())
            if include_headers:
                headers = {}
                for key in self.request.META:
                    if key in ["HTTP_AUTHORIZATION"]:
                        value = self.request.META.get(key)
                        if value and len(value) > 6:
                            headers[key.upper()] = "{}***{}".format(value[:value.find(' ')], value[-6:])
                sanitized["_headers_"] = headers
            if self.request:
                try:
                    self.request.request_log = PersistentLog.log(sanitized, level=5, component="rest", action="request", request=self.request)
                except Exception as err:
                    print(("PersistentLog.log failed with: '{}".format(str(err))))
                    print((repr(sanitized)))

    def getStrictType(self, value, field_type, default=None):
        if type(value) is field_type:
            return value

        try:
            if value == '':
                if field_type in [int, float]:
                    return field_type(0)

            if field_type in [int, str, float, str]:
                value = field_type(value)
            elif field_type is datetime:
                value = rest_helpers.parseDateTime(value)
            elif field_type is date:
                value = rest_helpers.parseDate(value, as_date=True)
            elif field_type is bool:
                return value in [1, '1', 'y', 'Y', 'on', 'T', 't', 'True', 'true']
            elif field_type is list:
                if value and value != NOTFOUND:
                    if type(value) in [dict, list]:
                        return value
                    elif "," in value:
                        return value.split(',')
                    return [value]
                return []
        except Exception:
            return default
        return value

    def getlist(self, key, default=None, split_spaces=False):
        res = self.get(key, default)
        if res and res != NOTFOUND:
            if type(res) in [dict, list]:
                return res
            elif "," in res:
                resp = res.split(',')
            elif split_spaces and " " in res:
                return res.split(' ')
            return [res]
        return []

    def _recursive_as_dict(self, root, key, value):
        gname = key[:key.find('.')]
        fname = key[key.find('.')+1:]
        if gname not in root:
            root[gname] = dict()
        nroot = root[gname]
        if '.' in fname:
            self._recursive_as_dict(nroot, fname, value)
        elif fname in nroot:
            if not isinstance(nroot[fname], list):
                nroot[fname] = [nroot[fname]]
            nroot[fname].append(value)
        else:
            nroot[fname] = value

    def normalizeData(self, data, normed=None):
        # this method takes "field1.field2 = value" to proper expaned dict
        if normed is None:
            normed = dict()
        is_qdict = isinstance(data, QueryDict)
        for field in data:
            if is_qdict:
                value = data.getlist(field)
                if len(value) <= 1:
                    value = data[field]
            else:
                value = data.get(field)
            if field.endswith('[]'):
                field = field[:-2]
            if "." in field:
                self._recursive_as_dict(normed, field, value)
            elif field in normed:
                if not isinstance(normed[field], list):
                    normed[field] = [normed[field]]
                normed[field].append(value)
            else:
                normed[field] = value
        return normed

    def toDict(self):
        self.__data = self.asDict()
        return self.__data

    def asDict(self, copy=False):
        if self.__data:
            if copy:
                return copy.deepcopy(self.__data)
            return self.__data
        data = None
        if self.request.method == "POST":
            data = self.request.POST
        else:
            data = self.request.GET

        d = self.normalizeData(data)

        if copy:
            return copy.deepcopy(d)
        return d

    def asUberDict(self):
        return UberDict.fromdict(self.__data)

    def toObject(self):
        return objict.fromdict(self.__data)

    def set(self, key, value):
        keys = key.split('.')
        data = self.__data
        depth = len(keys)
        for k in keys:
            depth -= 1
            if depth > 0:
                res = self.get(k, data=data)
                if res is None:
                    data[k] = {}
                    data = data[k]
                else:
                    data = res
            else:
                data[k] = value

    def removeNonASCII(self, value):
        return "".join([x for x in value if x in SAFE_ASCII])

    def getSafe(self, key, default=None, ignore_case=True, data=None, field_type=None):
        value = self.get(key, default, ignore_case, data, field_type)
        if isinstance(value, str):
            return self.removeNonASCII(value)
        return value

    def keys(self):
        if self.__data:
            return list(self.__data.keys())
        return []

    def fromKeys(self, keys):
        # generates a new UberDict, but only with the
        # passed in keys
        d = UberDict()
        for k in keys:
            v = self.get(k, NOTFOUND)
            if v != NOTFOUND:
                d[k] = v
        return d

    def get(self, key, default=None, ignore_case=True, data=None, field_type=None):
        # lets us pass in a list for keys and get the first match
        if type(key) is list:
            v = None
            for k in key:
                v = self.get(k, NOTFOUND, ignore_case, data, field_type)
                if v != NOTFOUND:
                    return v
            if v == NOTFOUND:
                return default
            return v

        # if type(key) not in [unicode, str]:
        # 	print self.__data
        # 	print "not valid key type: {0} {1}".format(key, type(key))
        # 	return default

        # try json first
        data = self.__data
        if not data:
            # no data in request
            return default

        if "." in key:
            keys = key.split('.')
            for k in keys:
                if ignore_case:
                    data = self.getIgnore(k, data=data)
                else:
                    data = self.getNormal(k, data=data)

                if data is NOTFOUND:
                    return default
            if field_type:
                if data is NOTFOUND or data is None:
                    return default
                return self.getStrictType(data, field_type, default)
            return data

        if ignore_case:
            data = self.getIgnore(key, data=data)
        else:
            data = self.getNormal(key, data=data)

        if data is NOTFOUND:
            return default
        if field_type:
            if data is None:
                return default
            return self.getStrictType(data, field_type, default)
        return data
