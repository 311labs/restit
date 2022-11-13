from django.forms import ModelForm, fields
from django.forms.widgets import ClearableFileInput
from django.core.files.uploadedfile import UploadedFile
from django.core import validators
from django.utils.encoding import smart_text

from .views import chunkUploadedFile

import re
from datetime import datetime, date

class ModelFormWithMeta(ModelForm):
    def __init__(self, *args, **kwargs):
        ret = super(ModelFormWithMeta, self).__init__(*args, **kwargs)
        if self.instance:
            rel = getattr(self.instance, self.Meta.meta_set)
            extension = getattr(self.Meta, 'meta_fields_extension', ())
            extended = getattr(self.Meta, 'meta_extended_fields', {})
            for f in self.Meta.meta_fields:
                keyval = f
                value_field = self.Meta.meta_fields[f]
                values = value_field.split('.', 1)
                if len(values) == 2:
                    keyval = values[0]
                    value_field = values[1]

                args = { getattr(self.Meta, 'meta_key', 'key'): keyval }
                m = rel.filter(**args)[:1]
                if len(m) > 0:
                    self.initial[f] = getattr(m[0], value_field, None)
                    for e in extension:
                        self.initial[f + "__" + e] = getattr(m[0], e, None)
                    for e in extended.get(f, []):
                        self.initial[extended[f][e]] = getattr(m[0], e, None)

        return ret

    def _save_meta(self):
        rel = getattr(self.instance, self.Meta.meta_set)
        extension = getattr(self.Meta, 'meta_fields_extension', ())
        extended = getattr(self.Meta, 'meta_extended_fields', {})
        for f in self.Meta.meta_fields:
            keyval = f
            value_field = self.Meta.meta_fields[f]
            values = value_field.split('.', 1)
            if len(values) == 2:
                keyval = values[0]
                value_field = values[1]

            meta_key = getattr(self.Meta, 'meta_key', 'key')
            m = rel.filter(**{ meta_key: keyval })[:1]

            # all meta attributes to be changed
            mattr = {}
            if f in self.data or self.cleaned_data.get(f):
                mattr[value_field] = self.cleaned_data[f]
            for e in extension:
                ef = f + "__" + e
                if ef in self.data:
                    mattr[e] = self.cleaned_data[ef]
            if f in extended:
                for e in extended[f]:
                    if e in self.data:
                        mattr[extended[f][e]] = self.data[e]

            if len(mattr) > 0:
                if len(m) == 0 and (f in self.data or self.cleaned_data.get(f)):
                    # new relationship
                    mattr[meta_key] = keyval
                    rel.create(**mattr)
                elif len(m) > 0:
                    # update existing
                    for f in mattr:
                        setattr(m[0], f, mattr[f])
                        m[0].save()

    def save(self, commit=True):
        def save_meta():
            self._save_meta_m2m()
            self._save_meta()

        instance = super(ModelFormWithMeta, self).save(commit=commit)
        if commit:
            save_meta()
        else:
            self._save_meta_m2m = self.save_m2m
            self.save_m2m = save_meta
        return instance

class ResumableFileInput(ClearableFileInput):
    def value_from_datadict(self, data, files, name):
        upload = super(ResumableFileInput, self).value_from_datadict(data, files, name)
        if not upload:
            if name + '.path' in data and name + '.name' in data and name + '.content_type' in data and name + '.size' in data:
                try:
                    f = open(data.get(name + '.path'))
                except OSError:
                    pass
                else:
                    upload = UploadedFile(file=f, name=data.get(name + '.name'), content_type=data.get(name + '.content_type'), size=data.get(name + '.size'))
        if not upload:
            if name + '_sessionid' in data:
                try:
                    upload = chunkUploadedFile(data.get('__request'), data.get(name + '_sessionid'))
                except OSError:
                    pass

        if upload:
            files[name] = upload
        return upload

class DateField(fields.DateField):
    def to_python(self, value):
        if value == None or value == '':
            return None
        elif type(value) in (int,float):
            return date.fromtimestamp(value)
        elif type(value) in (str,str) and re.match('^-?[0-9]+$', value):
            try:
                return date.fromtimestamp(int(value))
            except:
                pass
        if type(value) is datetime:
            return value.date()
        return super(fields.DateField, self).to_python(value)

class DateTimeField(fields.DateTimeField):
    def __init__(self, *args, **kwargs):
        ret = super(fields.DateTimeField, self).__init__(*args, **kwargs)
        
    def to_python(self, value):
        if value == None or value == '':
            return None
        elif type(value) in (int,float):
            return datetime.fromtimestamp(value)
        elif type(value) in (str,str) and re.match('^-?[0-9]+$', value):
            try:
                return datetime.fromtimestamp(int(value))
            except:
                pass
        return super(fields.DateTimeField, self).to_python(value)

class CommaSeparatedListField(fields.Field):
    def __init__(self, max_items=None, min_items=None, *args, **kwargs):
        self.max_items, self.min_items = max_items, min_items
        super(CommaSeparatedListField, self).__init__(*args, **kwargs)
        if min_items is not None:
            self.validators.append(validators.MinLengthValidator(min_items))
        if max_items is not None:
            self.validators.append(validators.MaxLengthValidator(max_items))
                
    def to_python(self, value):
        if value in validators.EMPTY_VALUES:
            return []
        
        if type(value) in (str, str):
            value = value.split(',')

        ret = []
        for t in value:
            t = t.strip()
            if t:
                ret.append(str(t))

        return ret
