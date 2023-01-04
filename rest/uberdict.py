__version_info__ = (0, 3, 0)
__version__ = '.'.join(map(str, __version_info__))

ALL = ['UberDict']

import sys, os
import json
import datetime
import time
from decimal import Decimal

import zlib
import base64

# py2/py3 compatibility
if sys.version_info[0] == 2:
    def iteritems(d):
        return iter(list(d.items()))
else:
    def iteritems(d):
        return list(d.items())


# For internal use only as a value that can be used as a default
# and should never exist in a dict.
_MISSING = object()
# we need these for DJANGO Fields
_MISSING_RAISE_ON_KEYS = ["resolve_expression", "prepare_database_save", "as_sql", "get_placeholder"]

class UberDict(dict):

    """
    A dict that supports attribute-style access and hierarchical keys.

    See `__getitem__` for details of how hierarchical keys are handled,
    and `__getattr__` for details on attribute-style access.

    Subclasses may define a '__missing__' method (must be an instance method
    defined on the class and not just an instance variable) that accepts one
    parameter. If such a method is defined, then a call to `my_UberDict[key]`
    (or the equivalent `my_UberDict.__getitem__(key)`) that fails will call
    the '__missing__' method with the key as the parameter and return the
    result of that call (or raise any exception the call raises).
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize a new `UberDict` using `dict.__init__`.

        When passing in a dict arg, this won't do any special
        handling of values that are dicts. They will remain plain dicts inside
        the `UberDict`. For a recursive init that will convert all
        dict values in a dict to UberDicts, use `UberDict.fromdict`.

        Likewise, dotted keys will not be treated specially, so something
        like `UberDict({'a.b': 'a.b'})` is equivalent to `ud = UberDict()` followed
        by `setattr(ud, 'a.b', 'a.b')`.
        """
        dict.__init__(self, *args, **kwargs)

    def __raise_on_missing__(self, key):
        # you can override this to put keys you want to override on missing or all keys
        return key in _MISSING_RAISE_ON_KEYS

    def __getitem__(self, key):
        """
        Get mapped value for given `key`, or raise `KeyError` if no such
        mapping.

        The `key` may be any value that is valid for a plain `dict`. If the
        `key` is a dotted key (a string like 'a.b' containing one or more
        '.' characters), then the key will be split on '.' and interpreted
        as a sequence of `__getitem__` calls. For example,
        `d.__getitem__('a.b')` would be interpreted as (approximately)
        `d.__getitem__('a').__getitem__('b')`. If the key is not a dotted
        it is treated normally.

        :exceptions:
        - KeyError: if there is no such key on a dict (or object that supports
          `__getitem__`) at any level of the dotted-key traversal.
        - TypeError: if key is not hashable or if an object at some point
          in the dotted-key traversal does not support `__getitem__`.
        """
        if not isinstance(key, str) or '.' not in key:
            return dict.__getitem__(self, key)
        try:
            obj, token = _descend(self, key)
            return _get(obj, token)
        except KeyError:
            # if '__missing__' is defined on the class, then we can delegate
            # to that, but we don't delegate otherwise for consistency with
            # plain 'dict' behavior, which requires '__missing__' to be an
            # instance method and not just an instance variable.
            if hasattr(type(self), '__missing__'):
                return self.__missing__(key)
            raise

    def __setitem__(self, key, value):
        """
        Set `value` for given `key`.

        See `__getitem__` for details of how `key` is intepreted if it is a
        dotted key and for exceptions that may be raised.
        """
        if not isinstance(key, str) or '.' not in key:
            return dict.__setitem__(self, key, value)

        obj, token = _descend(self, key)
        return dict.__setitem__(obj, token, value)

    def __delitem__(self, key):
        """
        Remove mapping for `key` in self.

        See `__getitem__` for details of how `key` is intepreted if it is a
        dotted key and for exceptions that may be raised.
        """
        if not isinstance(key, str) or '.' not in key:
            dict.__delitem__(self, key)
            return
        obj, token = _descend(self, key)
        del obj[token]

    def __getattr__(self, key):
        try:
            # no special treatement for dotted keys, but we need to use
            # 'get' rather than '__getitem__' in order to avoid using
            # '__missing__' if key is not in dict
            val = dict.get(self, key, _MISSING)
            if val is _MISSING:
                if self.__raise_on_missing__(key):
                    raise AttributeError("no attribute '%s'" % (key,))
                return None
            return val
        except KeyError as e:
            raise AttributeError("no attribute '%s'" % (e.args[0],))

    def __setattr__(self, key, value):
        # normal setattr behavior, except we put it in the dict
        # instead of setting an attribute (i.e., dotted keys are
        # treated as plain keys)
        dict.__setitem__(self, key, value)

    def __delattr__(self, key):
        try:
            # no special handling of dotted keys
            dict.__delitem__(self, key)
        except KeyError as e:
            raise AttributeError("no attribute '%s'" % (e.args[0]))

    def __reduce__(self):
        # pickle the contents of a UberDict as a list of items;
        # __getstate__ and __setstate__ aren't needed
        constructor = self.__class__
        instance_args = (list(iteritems(self)),)
        return constructor, instance_args

    def get(self, key, default=None):
        # We can't use self[key] to support `get` here, because a missing key
        # should return the `default` and should not use a `__missing__`
        # method if one is defined (as happens for self[key]).

        # this will grab the first key in the key list and return the value
        if type(key) is list:
            for k in key:
                v = self.get(k, _MISSING)
                if v != _MISSING:
                    return v
            return default

        if not isinstance(key, str) or '.' not in key:
            return dict.get(self, key, default)
        try:
            obj, token = _descend(self, key)
            return _get(obj, token)
        except KeyError:
            return default

    def sort(self, by_value=False, reverse=False):
        if by_value:
            return self.sortByValue(reverse=reverse)
        keys = list(self.sortKeys(reverse=reverse))
        old = self.copy()
        self.clear()
        for key in keys:
            self[key] = old[key]
        return self

    def sortByValue(self, reverse=False):
        marklist = sorted(self.items(), key=lambda x:x[1], reverse=reverse)
        self.clear()
        for key, value in marklist:
            self[key] = value
        return self

    def sortKeys(self, reverse=False):
        return sorted(self.keys(), reverse=reverse)

    def find(self, key, default=None, data=None):
        # this will search the dict for the first key it finds that matches this
        if data is None:
            data = self
        v = data.get(key, _MISSING)
        if v != _MISSING:
            return v
        for k in data:
            d = data.get(k)
            if isinstance(d, dict):
                v = self.find(key, _MISSING, d)
                if v != _MISSING:
                    return v
        return default

    def changes(self, dict2, ignore_keys=None):
        changes = UberDict()
        if not bool(dict2):
            dict2 = UberDict()
        for k in self:
            if ignore_keys and k in ignore_keys:
                continue
            v1 = self.get(k, None)
            v2 = dict2.get(k, None)
            if isinstance(v1, dict):
                if not isinstance(v1, UberDict):
                    v1 = UberDict.fromdict(v1)
                v = v1.changes(v2)
                if len(v):
                    changes[k] = v
            elif isinstance(v1, list) and isinstance(v2, list):
                if bool(set(v1).intersection(set(v2))):
                    changes[k] = v2
            else:
                if v1 != v2:
                    changes[k] = v2
        return changes

    def fromKeys(self, keys):
        # generates a new UberDict, but only with the
        # passed in keys
        d = UberDict()
        for k in keys:
            v = dict.__getitem__(self, k)
            d[k] = v
        return d

    @classmethod
    def fromkeys(self, seq, value=None):
        return UberDict((elem, value) for elem in seq)

    @classmethod
    def fromdict(cls, mapping):
        """
        Create a new `UberDict` from the given `mapping` dict.

        The resulting `UberDict` will be equivalent to the input
        `mapping` dict but with all dict instances (recursively)
        converted to an `UberDict` instance.  If you don't want
        this behavior (i.e., you want sub-dicts to remain plain dicts),
        use `UberDict(mapping)` instead.
        """
        if isinstance(mapping, list):
            out = []
            for lv in mapping:
                out.append(cls.fromdict(lv))
            return out
        elif isinstance(mapping, dict):
            ud = cls()
            for k in mapping:
                v = dict.__getitem__(mapping, k)  # okay for py2/py3
                if isinstance(v, dict):
                    v = cls.fromdict(v)
                elif isinstance(v, list):
                    v = cls.fromdict(v)
                # handle keys like 'key1.key2.key3'
                if '.' in k:
                    skeys = k.split('.')
                    nd = ud
                    while len(skeys) > 1:
                        skey = skeys.pop(0)
                        nd2 = nd.get(skey, cls())
                        dict.__setitem__(nd, skey, nd2)
                        nd = nd2
                    skey = skeys.pop(0)
                    dict.__setitem__(nd, skey, v)
                    continue
                dict.__setitem__(ud, k, v)
            return ud
        elif mapping is None:
            return cls()
        return mapping

    @classmethod
    def fromZIP(cls, data, ignore_errors=True):
        if ignore_errors:
            if not isinstance(data, bytes):
                data = base64.b64decode(data.encode('utf-8'))
            return cls.fromJSON(zlib.decompress(data))
        try:
            if not isinstance(data, bytes):
                data = base64.b64decode(data.encode('utf-8'))
            return cls.fromJSON(zlib.decompress(data))
        except Exception as err:
            pass
        return cls()

    def toZIP(self, as_string=False):
        # compress the dictionary to a zip
        cout = zlib.compress(str.encode(self.toJSON(as_string=True)))
        if as_string:
            return base64.b64encode(cout).decode('utf-8')
        return cout

    def save(self, path):
        with open(path, "w") as f:
            f.write(self.toJSON(as_string=True))
            f.write("\n")

    @classmethod
    def fromFile(cls, path, ignore_errors=False):
        if not os.path.isfile(path) or os.stat(path).st_size == 0:
            f = open(path, "w")
            f.write("{}")
            f.close()
        if not ignore_errors:
            with open(path, "r") as f:
                return cls.fromJSON(f.read())
        try:
            with open(path, "r") as f:
                return cls.fromJSON(f.read())
        except:
            pass
        return cls()

    @classmethod
    def fromJSON(cls, text, ignore_errors=True):
        if not ignore_errors:
            return cls.fromdict(json.loads(text))
        try:
            return cls.fromdict(json.loads(text))
        except Exception:
            pass
        return cls()

    def toJSON(self, as_string=False, fields=None, exclude=None):
        """
        By default this create a json ready dictionary
        or string
        """
        d = dict()
        src = self
        if fields:
            src = self.fromKeys(fields)

        for k in src:
            v = dict.__getitem__(src, k)
            t = type(v)
            if exclude and k in exclude:
                continue
            elif isinstance(v, UberDict):
                d[k] = v.toJSON()
            elif isinstance(v, datetime.date):
                d[k] = time.mktime(v.timetuple())
            elif isinstance(v, datetime.date):
                d[k] = v.strftime("%Y/%m/%d")
            elif isinstance(v, Decimal):
                d[k] = float(v)
            elif hasattr(v, "id"):
                d[k] = v.id
            else:
                d[k] = v
        if as_string:
            return json.dumps(d)
        return d

    def asDict(self, fields=None):
        return self.todict(fields)

    def todict(self, fields=None):
        """
        Create a plain `dict` from this `UberDict`.

        The resulting `dict` will be equivalent to this `UberDict`
        but with every `UberDict` value (recursively) converted to
        a plain `dict` instance.
        """
        d = dict()
        for k in self:
            v = dict.__getitem__(self, k)
            if isinstance(v, UberDict):
                v = v.todict()
            d[k] = v
        return d

    def copy(self):
        """
        Return a shallow copy of this `UberDict`.

        For a deep copy, use `UberDict.fromdict` (as long as there aren't
        plain dict values that you don't want converted to `UberDict`).
        """
        return UberDict(self)

    def extend(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, dict):
                self.extend(**arg)
        for key in kwargs:
            self[key] = kwargs[key]
        return self

    def setdefault(self, key, default=None):
        """
        If `key` is in the dictionary, return its value.
        If not, insert `key` with a value of `default` and return `default`,
        which defaults to `None`.
        """
        val = self.get(key, _MISSING)
        if val is _MISSING:
            val = default
            self[key] = default
        return val

    def set(self, key, value):
        if "." in key:
            data = self
            tokens = key.split('.')
            for token in tokens[:-1]:
                v = data.get(token)
                if v is None:
                    v = UberDict()
                data[token] = v
                data = v
            data[tokens[-1]] = value
            return None
        self[key] = value
        return None

    def __contains__(self, key):
        return self.get(key, _MISSING) is not _MISSING

    def pop(self, key, *args):
        if not isinstance(key, str) or '.' not in key:
            return dict.pop(self, key, *args)
        try:
            obj, token = _descend(self, key)
        except KeyError:
            if args:
                return args[0]
            raise
        else:
            return dict.pop(obj, token, *args)

    def __dir__(self):
        """
        Expose the expected instance and class attributes and methods
        for the builtin `dir` method, as well as the top-level keys that
        are stored.
        """
        return sorted(set(dir(UberDict)) | set(self.keys()))


# helper to do careful and consistent `obj[name]`
def _get(obj, name):
    """
    Get the indexable value with given `name` from `obj`, which may be
    a `dict` (or subclass) or a non-dict that has a `__getitem__` method.
    """
    try:
        # try to get value using dict's __getitem__ descriptor first
        return dict.__getitem__(obj, name)
    except TypeError:
        # if it's a dict, then preserve the TypeError
        if isinstance(obj, dict):
            raise
        # otherwise try one last time, relying on __getitem__ if any
        return obj[name]


# helper for common use case of traversing a path like 'a.b.c.d'
# to get the 'a.b.c' object and do something to it with the 'd' token
def _descend(obj, key):
    """
    Descend on `obj` by splitting `key` on '.' (`key` must contain at least
    one '.') and using `get` on each token that results from splitting
    to fetch the successive child elements, stopping on the next-to-last.

     A `__getitem__` would do `dict.__getitem__(value, token)` with the
     result, and a `__setitem__` would do `dict.__setitem__(value, token, v)`.

    :returns:
    (value, token) - `value` is the next-to-last object found, and
    `token` is the last token in the `key` (the only one that wasn't consumed
    yet).
    """
    tokens = key.split('.')
    assert len(tokens) > 1
    value = obj
    for token in tokens[:-1]:
        value = _get(value, token)
    return value, tokens[-1]
