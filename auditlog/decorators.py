from .models import *

from sessionlog.models import SessionLog

from django.db.models.signals import post_init, m2m_changed
from django.db.models.fields.related import ManyToManyField
from django.core.exceptions import FieldDoesNotExist

from rest.middleware import get_request

import os
import sys
import inspect

try:
    from __main__ import AUDIT_DISABLED
except ImportError:
    AUDIT_DISABLED = False

def auditclass(fields=None, exclude=[]):
    """
    Audits field changes
    """

    def _store(self):
        if self.pk:
            self.__audit_old_data = dict((f, getattr(self, f)) for f in self.__audit_fields)
        else:
            self.__audit_old_data = {}

    def _post_init(sender, instance, **kwargs):
        _store(instance)

    def _logit(cls, pk, changes, skipstack=2):
        request = get_request()
        session = None
        user = None
        how = None
        referer = None

        if request:
            if request.user.is_authenticated:
                user = request.user
            session = SessionLog.GetSession(request)
            try:
                how = request.path
                referer = getattr(request, 'META', {}).get('HTTP_REFERER')
            except AttributeError:
                pass
            if not how:
                try:
                    how = sys.argv[0]
                    referer = ' '.join(sys.argv)
                except (AttributeError, IndexError):
                    pass
        
        stack = ', '.join(list("%s:%d:%s" % (os.path.basename(s[1]), s[2], s[3]) for s in inspect.stack()[skipstack:]))

        for k, v in list(changes.items()):
            AuditLog(
                model="%s.%s" % (cls._meta.app_label, cls._meta.model_name),
                pkey=pk,
                attribute=k,
                user=user,
                session=session,
                how=how,
                referer=referer,
                stack = stack,
                oldval = None if v[0] == None else str(v[0]),
                newval = None if v[1] == None else str(v[1]),
            ).save()

    def _m2m_changed(sender, instance, action, reverse, model, pk_set, using, **kwargs):
        oldval = None
        if action == 'post_clear':
            newval = 'CLEAR'
        elif action == 'post_add':
            newval = "ADD: "
            if not pk_set:
                return
        elif action == 'post_remove':
            newval = "REMOVE: "
            if not pk_set:
                return
        elif action == "pre_clear":
            pass
        else:
            return

        if reverse:
            mymodel = model
        else:
            mymodel = instance
        attname = None
        for f in mymodel._meta.many_to_many:
            if f.rel.through == sender:
                attname = f.attname
                break
        if not attname:
            return

        if action == "pre_clear":
            setattr(instance, '__audit_m2m_%s' % sender.__name__, ",".join(list(str(x) for x in getattr(instance, attname).all().values_list('pk', flat=True))))
            return
        if newval == "CLEAR":
            oldval = getattr(instance, '__audit_m2m_%s' % sender.__name__, '')

        if not pk_set:
            _logit(mymodel, instance.pk, {attname: (oldval, newval)}, skipstack=5)
        else:
            for pk in pk_set:
                if reverse:
                    _logit(mymodel, pk, {attname: (oldval, "%s%d" % (newval, instance.pk))}, skipstack=5)
                else:
                    _logit(mymodel, instance.pk, {attname: (oldval, "%s%d" % (newval, pk))}, skipstack=5)

    def inner(cls):
        # contains a local copy of the previous values of attributes
        cls.__audit_old_data = {}

        def has_changed(self, field):
            "Returns ``True`` if ``field`` has changed since initialization."
            return self.__audit_old_data.get(field) != getattr(self, field)
        cls.audit_has_changed = has_changed

        def old_value(self, field):
            "Returns the previous value of ``field``"
            return self.__audit_old_data.get(field)
        cls.audit_old_value = old_value

        def list_changed(self):
            "Returns a list of changed attributes."
            changed = {}
            for f in self.__audit_fields:
                if self.__audit_old_data.get(f) != getattr(self, f):
                    changed[f] = (self.__audit_old_data.get(f), getattr(self, f))
            return changed
        cls.audit_list_changed = list_changed

        # Ensure we are updating local attributes on model init
        post_init.connect(_post_init, sender=cls, weak=False)


        # Ensure we are updating local attributes on model save
        def save(self, *args, **kwargs):
            ret = save._original(self, *args, **kwargs)

            changes = self.audit_list_changed()
            if not changes:
                return ret

            _logit(self, self.pk, changes)
            _store(self)
            return ret
        save._original = cls.save
        cls.save = save

        def delete(self, *args, **kwargs):
            pk = self.pk
            ret = delete._original(self, *args, **kwargs)
            _logit(self, pk, {'*DELETE': (None,None,)})
            return ret
        delete._original = cls.delete
        cls.delete = delete
        
        if fields:
            afields = fields.copy()
        else:
            afields = []
            for f in cls._meta.fields + cls._meta.many_to_many:
                if getattr(f, 'auto_now', False) or getattr(f, 'auto_now_add', False) or getattr(f, 'primary_key', False):
                    continue
                afields.append(f.attname)
        for f in exclude:
            afields.remove(f)

        cls.__audit_fields = []
        cls.__audit_m2m_fields = []
        for f in afields:
            try:
                gf = cls._meta.get_field(f)
            except FieldDoesNotExist as e:
                if f[-3:] == '_id':
                    try:
                        gf = cls._meta.get_field(f[:-3])
                    except:
                        raise(e)
                else:
                    raise(e)
            if isinstance(gf, ManyToManyField):
                m2m_changed.connect(_m2m_changed, sender=gf.rel.through, weak=False)
                cls.__audit_m2m_fields.append(f)
            else:
                cls.__audit_fields.append(f)

            
        return cls

    if AUDIT_DISABLED:
        return lambda x: x
    return inner
