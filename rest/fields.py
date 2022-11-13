
from django.db import models
from django.forms.widgets import ClearableFileInput
from django.core.files.uploadedfile import UploadedFile
from django.core import validators
from .uberdict import UberDict
from .views import chunkUploadedFile
from .crypto import aes

import re
from datetime import datetime, date

try:
    import phonenumbers
except:
    phonenumbers = None

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

class DateField(models.DateField):
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
        return super(models.DateField, self).to_python(value)

class DateTimeField(models.DateTimeField):
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
        return super(models.DateTimeField, self).to_python(value)

from decimal import Decimal
class CurrencyField(models.DecimalField):
    def __init__(self, *args, **kwargs):
        default_value = kwargs.pop("default", 0.0)
        kwargs["default"] = default_value

        max_digits = kwargs.pop("max_digits", 12)
        kwargs["max_digits"] = max_digits

        decimal_places = kwargs.pop("decimal_places", 2)
        kwargs["decimal_places"] = decimal_places

        super(CurrencyField, self).__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection, *args, **kwargs):
        if value is None:
            return value
        if not isinstance(value, Decimal):
            value = Decimal(value)
        return value.quantize(Decimal("0.01"))

    def to_python(self, value):
        if value is None:
            return value
        if not isinstance(value, Decimal):
            value = Decimal(value)
        return value.quantize(Decimal("0.01"))

class FormattedField(models.CharField):
    TITLE = 1
    UPPERCASE = 2
    LOWERCASE = 3
    PHONE = 5

    def __init__(self, *args, **kwargs):
        self.format_kind = kwargs.pop('format', 0)
        max_length = kwargs.pop('max_length', 254)
        kwargs["max_length"] = max_length
        super(FormattedField, self).__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection, *args, **kwargs):
        return FormattedField.format(value, self.format_kind)

    def to_python(self, value):
        return FormattedField.format(value, self.format_kind)

    def get_prep_value(self, value):
        value = super(FormattedField, self).get_prep_value(value)
        return FormattedField.format(value, self.format_kind)

    @staticmethod
    def parsePhone(value, region):
        try:
            pp = phonenumbers.parse(value, region)
        except:
            return None
        return pp

    @staticmethod
    def format(value, format=0):
        if not value:
            return value
        if isinstance(value, list):
            # hot fix for some issues being seen
            value = " ".join(value)
        if format == FormattedField.UPPERCASE:
            return value.upper()
        elif format == FormattedField.LOWERCASE:
            return value.lower()
        elif format == FormattedField.TITLE:
            return value.title()
        elif format == FormattedField.PHONE:
            if phonenumbers:
                try:
                    x = phonenumbers.parse(value, "US")
                    if not x:
                        x = phonenumbers.parse(value, None)
                    if not x:
                        return value.replace(' ', '').replace('.', '-').replace('(', '').replace(')', '-')
                    return phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                except Exception as err:
                    print(("phone format error: '{}' .. error: {}".format(value, str(err))))
            else:
                return value.replace(' ', '').replace('.', '-').replace('(', '').replace(')', '-')
        return value

class CommaSeparatedListField(models.TextField):
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
        if isinstance(value, str):
            value = value.split(',')
        ret = []
        for t in value:
            if not isinstance(value, str):
                t = str(t)
            t = t.strip()
            if bool(t):
                ret.append(t)
        return ret

    def from_db_value(self, value, expression, connection, *args, **kwargs):
        return self.to_python(value)

    def to_string(self, value):
        if value is None:
            if not self.null and self.blank:
                return ""
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return ",".join(value)
        return value

    def get_prep_value(self, value):
        return self.to_string(value)

    def value_to_string(self, obj):
        return self.to_string(obj)


class JSONField(models.TextField):
    def __init__(self, *args, **kwargs):
        default_value = kwargs.pop("default", None)
        null = kwargs.pop("null", True)
        kwargs["default"] = default_value
        kwargs["null"] = null
        super(JSONField, self).__init__(*args, **kwargs)

    # def pre_save(self, model_instance, add):
    #     return super(JSONField, self).pre_save(model_instance, add)

    def to_python(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UberDict.fromJSON(value)
        elif isinstance(value, dict) and not hasattr(value, "fromdict"):
            value = UberDict.fromdict(value)
        return value

    def from_db_value(self, value, expression, connection, *args, **kwargs):
        return self.to_python(value)

    def to_string(self, value):
        if value is None:
            if not self.null and self.blank:
                return ""
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            if not hasattr(value, "toJSON"):
                value = UberDict.fromdict(value)
            return value.toJSON(as_string=True)
        return value

    def get_prep_value(self, value):
        return self.to_string(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        return super().get_db_prep_value(self.to_string(value), connection, prepared)

    # def get_db_prep_save(self, value, connection):
    #     return super().get_db_prep_save(value, connection)

    def value_to_string(self, obj):
        return self.get_prep_value(obj)


class EncryptedField(models.TextField):
    ENCRYPTION_KEY = "&F)J@NcRfUjXn2r5u8x/A?D*G-KaPdSgVkYp3s6v9y$B&E)H+MbQeThWmZq4t7w!z%C*F-JaNcRfUjXn2r5u8x/A?D(G+KbPeSgVkYp3s6v9y$B&E)H@McQfTjWmZq4t"

    def __init__(self, *args, **kwargs):
        default_value = kwargs.pop("default", None)
        null = kwargs.pop("null", True)
        kwargs["default"] = default_value
        kwargs["null"] = null
        super(EncryptedField, self).__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection, *args, **kwargs):
        if value is None:
            return value
        return EncryptedField.decrypt(value)

    def to_python(self, value):
        if value is None:
            return value
        return EncryptedField.decrypt(value)

    def get_prep_value(self, value):
        if value is None:
            if not self.null and self.blank:
                return ""
            return None
        return EncryptedField.encrypt(value)

    @staticmethod
    def encrypt(text):
    	return aes.encrypt(EncryptedField.ENCRYPTION_KEY, text)

    @staticmethod
    def decrypt(encrypted):
        return aes.decrypt(EncryptedField.ENCRYPTION_KEY, encrypted)