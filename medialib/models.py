# required for datamodel
from django.db import models
from account.models import User, Group
from django.db.models import Q

# required for accessors
from . import stores

from django.template import RequestContext
from django.utils.http import base36_to_int, int_to_base36
from django.utils.crypto import salted_hmac
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.files.uploadedfile import InMemoryUploadedFile
import urllib.request, urllib.error, urllib.parse
from urllib.parse import urlparse
from datetime import datetime, date
import os
import hashlib
import time
from django.conf import settings
import mimetypes
import tempfile

from medialib import utils
from rest.models import RestModel, MetaDataBase, MetaDataModel
from rest.decorators import rest_async

from taskqueue.models import Task


TASKQUEUE_RENDERING = getattr(settings, "TASKQUEUE_RENDERING", False)

from rest.log import getLogger
logger = getLogger("medialib", filename="medialib.log")

MediaKinds = (
    ('I', 'Image'),
    ('V', 'Video'),
    ('D', 'Audio'),
    ('L', 'Live Video'),
    ('A', 'Live Archive'),
    ('S', 'Video Segment'),
    ('E', 'External Link'),
    ('T', 'Text'),
    ('*', 'Unknown'),
)
RenditionKinds = (
    ('I', 'Image'),
    ('V', 'Video'),
    ('D', 'Audio'),
    ('L', 'Live Stream'),
#   ('A', 'Live Archive *unused*'),
#   ('S', 'Video Segment *unused*'),
    ('N', 'Animated Image'),
    ('E', 'External Link'),
    ('T', 'Text'),
    ('*', 'Unknown'),
)
MediaStates = (
    (0, "Inactive"),
    (1, "Deleted"),
    (50, "Archived"),
    (90, "Hold"),
    (100, "Initial render pending"),
    (101, "Render pending"),
    (102, "Rendering"),
    (110, "Render failed"),
    (111, "Validation failed"),
    (120, "Render ending"),
    (200, "Active"),
)
RenditionParameterKinds = (
    ('S', 'String'),
    ('I', 'Integer'),
    ('F', 'Float'),
    ('B', 'Boolean'),
    ('C', 'Choices'),
)
RenderingEngineStates = (
    ('S', 'Starting'),
    ('I', 'Idle'),
    ('R', 'Rendering'),
    ('0', 'Stopped'),
)

class RenditionParameter(models.Model):
    """
    Available parameters for all renditions
    """
    name = models.CharField(max_length=127, help_text="Parameter name")
    description = models.TextField(null=True, blank=True, help_text="Parameter description")
    required = models.BooleanField(default=False, help_text="Whether is required")
    kind = models.CharField(max_length=1, choices=RenditionParameterKinds, help_text="Type of value")
    choices = models.TextField(null=True, blank=True, help_text="Comma separated list of choices")

    def __str__(self):
        return self.name

    def validate_setting(self, setting):
        if self.kind == 'S':
            return str(setting).strip()
        if self.kind == 'I':
            return int(setting)
        if self.kind == 'F':
            return float(setting)
        if self.kind == 'B':
            if str(setting).lower().strip() in ('1', 'true', 'yes'):
                return True
            elif str(setting).lower().strip() in ('0', 'false', 'no', 'none', ''):
                return False
            raise ValueError("setting is not boolean")
        if self.kind == 'C':
            s = str(setting).lower().strip()
            if s in list(x.lower().strip() for x in self.choices.split(",")):
                return setting.strip()
            raise ValueError("setting is not valid choice")
        raise ValueError("invalid parameter kind")


class RenditionPreset(models.Model):
    """
    Predefined basic rendition settings
    """
    name = models.CharField(max_length=127, help_text="Name of preset")
    short_name = models.SlugField(max_length=32, db_index=True, unique=True, help_text="short name")
    description = models.TextField(null=True, blank=True, help_text="Preset description")
    stage = models.IntegerField(help_text="0-100: run when uploaded, >100: run later")
    parameters = models.ManyToManyField(RenditionParameter, through='RenditionPresetParameterSetting', blank=True, help_text="Default values for parameters")
    configurable_parameters = models.ManyToManyField(RenditionParameter, related_name='applicable_renditions', blank=True, help_text="All parameters that can be set by user")
    default_use = models.CharField(max_length=32, null=True, blank=True, help_text="The default intended use for this rendition types based on this preset")
    applicable_kinds = models.CharField(max_length=16, help_text="Applicable rendition kinds")
    module_name = models.SlugField(max_length=32, db_index=True, help_text="module name")

    def is_distribution(self):
        try:
            return RenditionPresetParameterSetting.objects.get(renditionPreset=self, parameter__name="is_distribution").setting
        except RenditionPresetParameterSetting.DoesNotExist:
            return False

    def __str__(self):
        return self.name

class AccountConfig(models.Model):
    name = models.CharField(max_length=127, help_text="Name config group")
    owner = models.ForeignKey(User, help_text="owner of config", on_delete=models.CASCADE)
    applicable_preset = models.ForeignKey(RenditionPreset, related_name="+", help_text="Applicable preset (info only)", blank=True, null=True, on_delete=models.CASCADE)
    parameters = models.ManyToManyField(RenditionParameter, through='AccountConfigParameterSetting', blank=True, help_text="Values for parameters")

    def __str__(self):
        return self.name

class RenditionDefinition(models.Model):
    """
    User defined rendition types, refined based on RenditionPreset
    """

    class Meta:
        ordering = ["preset__stage", "id"]

    name = models.CharField(max_length=127, db_index=True, help_text="Definition name")
    description = models.TextField(null=True, blank=True, help_text="Definition description")
    preset = models.ForeignKey(RenditionPreset, related_name="+", help_text="Base preset", on_delete=models.CASCADE)
    parameters = models.ManyToManyField(RenditionParameter, through='RenditionDefinitionParameterSetting', help_text="Configured parameters (override values only)")
    active = models.BooleanField(default=True, help_text="Should use for new media")
    use = models.CharField(max_length=32, null=True, blank=True, help_text="The intended use for this rendition type")
    configSet = models.ManyToManyField(AccountConfig, help_text="Additional account config set defaults", blank=True)
    depend = models.CharField(max_length=127, blank=True, db_index=True, help_text="Depends on (use name)")

    def setParameter(self, key, value, kind="I"):
        p = self.renditiondefinitionparametersetting_set.filter(parameter__name=key).last()
        if p is None:
            param = RenditionParameter.objects.filter(name=key).last()
            if param is None:
                param = RenditionParameter(name=key, description=key, kind=kind)
                param.save()
            p = RenditionDefinitionParameterSetting(renditionDefinition=self, parameter=param, setting=value)
            p.save()
        p.setting = value
        p.save()

    def getParameter(self, parameter, item=None):
        if isinstance(parameter, str):
            p = self.renditiondefinitionparametersetting_set.filter(parameter__name=parameter).last()
            if p is not None:
                return p.setting
            p = self.preset.renditionpresetparametersetting_set.filter(parameter__name=parameter).last()
            if p is not None:
                return p.setting
            parameter = RenditionParameter.objects.get(name=parameter)
        if item:
            try:
                return self.mediaitemparametersetting_set.get(parameter=parameter).setting
            except ObjectDoesNotExist:
                pass
        try:
            return self.renditiondefinitionparametersetting_set.get(parameter=parameter).setting
        except ObjectDoesNotExist:
            pass

        for cfg in self.configSet.all().order_by('-id'):
            try:
                return cfg.accountconfigparametersetting_set.get(parameter=parameter).setting
            except ObjectDoesNotExist:
                pass

        try:
            return self.preset.renditionpresetparametersetting_set.get(parameter=parameter).setting
        except ObjectDoesNotExist:
            pass
        return None

    def getParameters(self, item=None):
        params = {}
        for p in self.preset.renditionpresetparametersetting_set.all():
            params[p.parameter.name] = (p.parameter, p.setting, True)
        for cfg in self.configSet.all().order_by('id'):
            for p in cfg.accountconfigparametersetting_set.all():
                params[p.parameter.name] = (p.parameter, p.setting, True)
        for p in self.renditiondefinitionparametersetting_set.all():
            params[p.parameter.name] = (p.parameter, p.setting, False)
        if item:
            for p in item.mediaitemparametersetting_set.all():
                params[p.parameter.name] = (p.parameter, p.setting, False)
        return params

    def __str__(self):
        return self.name

class RenditionSet(models.Model):
    """
    List applicable rendition definitions for a media type
    """

    name = models.CharField(max_length=127, db_index=True, help_text="Set name")
    renditions = models.ManyToManyField(RenditionDefinition, help_text="Renditions used", blank=True)
    kind = models.CharField(max_length=1, choices=MediaKinds, help_text="Kind of media this rendition set is for")
    default_set = models.BooleanField(default=False, help_text="Whether is global default")

    def __str__(self):
        return "%s: %s%s" % (self.kind, self.name, self.default_set and " (default)" or "")

class RenditionPresetParameterSetting(models.Model):
    """
    Key/Value parameter pairs per rendition preset
    """
    class Meta:
        unique_together = (('renditionPreset', 'parameter'),)
    renditionPreset = models.ForeignKey(RenditionPreset, help_text="Preset this pair belongs to", on_delete=models.CASCADE)
    parameter = models.ForeignKey(RenditionParameter, help_text="Parameter", on_delete=models.CASCADE)
    setting = models.CharField(max_length=127, null=True, blank=True, help_text="Value")

    def __str__(self):
        return "%s - %s" % (str(self.renditionPreset), str(self.parameter))

class AccountConfigParameterSetting(models.Model):
    """
    Key/Value parameter pairs per rendition preset
    """
    class Meta:
        unique_together = (('accountConfig', 'parameter'),)
    accountConfig = models.ForeignKey(AccountConfig, help_text="Config this pair belongs to", on_delete=models.CASCADE)
    parameter = models.ForeignKey(RenditionParameter, help_text="Parameter", on_delete=models.CASCADE)
    setting = models.CharField(max_length=127, null=True, blank=True, help_text="Value")

    def __str__(self):
        return "%s - %s" % (str(self.accountConfig), str(self.parameter))

class RenditionDefinitionParameterSetting(models.Model):
    """
    Key/Value parameter pairs per rendition definition
    """
    class Meta:
        unique_together = (('renditionDefinition', 'parameter'),)
    renditionDefinition = models.ForeignKey(RenditionDefinition, help_text="Definition this pair belongs to", on_delete=models.CASCADE)
    parameter = models.ForeignKey(RenditionParameter, help_text="Parameter", on_delete=models.CASCADE)
    setting = models.CharField(max_length=127, null=True, blank=True, help_text="Value")

    def __init__(self, *args, **kwargs):
        try:
            default = kwargs.pop('default')
        except KeyError:
            pass
        else:
            self.default = default
        return super(RenditionDefinitionParameterSetting, self).__init__(*args, **kwargs)

    def __str__(self):
        return "%s - %s" % (str(self.renditionDefinition), str(self.parameter))

class MediaLibrary(models.Model, RestModel):
    """
    Media Library (one per user)
    """
    VIEW_PERMS = ["view_media"]
    SAVE_PERMS = ["manage_media"]
    OWNER_FIELD = "owner"
    name = models.CharField(max_length=127, help_text="name of media library")
    description = models.TextField(null=True, blank=True, help_text="description of media library")
    owner = models.ForeignKey(User, help_text="owner of library", related_name="libraries", blank=True, null=True, default=None, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, related_name="libraries", help_text="group owner of library", blank=True, default=None, null=True, on_delete=models.CASCADE)
    rendition_sets = models.ManyToManyField(RenditionSet, blank=True, help_text="list of RenditionSets used in this library")
    allowed_kinds = models.CharField(max_length=127, null=True, blank=True, help_text="allowed object kinds (null=ALL)")
    acl_default = ((250, None, "R"),)
    acl_override_user = 'owner'

    class Meta:
        permissions = (
            ("can_manage", "Can manage medialib directly"),
        )

    def __str__(self):
        return self.name + ' : ' + str(self.owner)

    def allowed_kinds_list(self):
        if self.allowed_kinds:
            return list(self.allowed_kinds)
        else:
            return list(x[0] for x in MediaKinds)

    def default_store(self):
        try:
            return settings.MEDIALIB_STORE[self.id]
        except (KeyError, AttributeError):
            return settings.MEDIALIB_DEFAULT_STORE

class MediaItem(models.Model, RestModel, MetaDataModel):
    """
    Media Item (a video or image)
    """
    class RestMeta:
        VIEW_PERMS = ["view_media"]
        SAVE_PERMS = ["manage_media"]
        OWNER_FIELD = "owner"
        GRAPHS = {
            "simple": {
                "fields": [
                    'id',
                    'name',
                    'kind',
                    'state',
                    ('thumbnail_url', "thumbnail"),
                ]
            },
            "basic": {
                "fields": [
                    'id',
                    "created",
                    'name',
                    'kind',
                    'state',
                    ('get_state_display', 'state_display'),
                    'duration',
                    ('thumbnail_url', "thumbnail"),
                    ('smart_renditions', "renditions"),
                ]
            },
            "default": {
                "extra":["metadata"],
                "graphs":{
                    "self":"basic",
                }
            }
        }

    library = models.ForeignKey(MediaLibrary, related_name='items', help_text="Library this item belongs to", null=True, blank=True, default=None, on_delete=models.CASCADE)
    owner = models.ForeignKey(User, help_text="Owner of item", null=True, blank=True, default=None, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, help_text="Owner of item", null=True, blank=True, default=None, on_delete=models.CASCADE)
    name = models.CharField(max_length=127, help_text="Name of item")
    description = models.TextField(blank=True, help_text="Description of item")
    created = models.DateTimeField(auto_now_add=True, editable=False, help_text="When item was created")
    kind = models.CharField(max_length=1, choices=MediaKinds, help_text="Kind of media")
    state = models.IntegerField(choices=MediaStates, help_text="Rendering state of item")
    render_error = models.TextField(null=True, blank=True, help_text="Any render error messages")
    acl_override_user = 'owner'
    acl_parent = 'library'

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        if 'newfile' in kwargs:
            self.newfile = kwargs.pop('newfile')
        elif 'base64_data' in kwargs:
            self.base64_data = kwargs.pop('base64_data')
            if self.base64_data.startswith("data:"):
                self.base64_data = self.base64_data[self.base64_data.find(',')+1:]
        elif 'newurl' in kwargs:
            self.newurl = kwargs.pop('newurl')
        elif 'downloadurl' in kwargs:
            self.downloadurl = kwargs.pop('downloadurl')
        super(MediaItem, self).__init__(*args, **kwargs)
        self.old_state = self.state

    def onRestCanSave(self, request):
        # must throw an exception if cannot save
        return True

    @staticmethod
    def _timestamp():
        return (date.today() - date(2010,1,1)).days

    @staticmethod
    def guessMediaKind(fileobj):
        return utils.guessMediaKind(fileobj)

    def token(self, timestamp=None):
        if timestamp == None:
            timestamp = self._timestamp()
        ts_b36 = int_to_base36(timestamp)
        hash = salted_hmac(settings.SECRET_KEY, ts_b36 + str(self.id) + str(self.created)).hexdigest()[::2]
        return '%s.%s' % (ts_b36, hash)

    def id_token(self, timestamp=None):
        return '%d.%s' % (self.id, self.token(timestamp=timestamp))

    def id_token_perpectual(self):
        return self.id_token(timestamp=0)

    def check_token(self, token):
        if not token:
            return False
        ts_b36 = token.split(".")[0]
        timestamp = base36_to_int(ts_b36)
        nowts = self._timestamp()
        if timestamp > 0 and (timestamp > nowts or timestamp < nowts-2):
            return False
        return "%d.%s" % (self.id, token) == self.id_token(timestamp)

    def default_store(self):
        if self.library:
            return self.library.default_store()
        return settings.MEDIALIB_DEFAULT_STORE

    def uses(self):
        """
        List uses available for this item
        """
        return list(self.renditions.values('use').distinct().values_list('use', flat=True))

    def rerender(self):
        self.deleteRenditions()
        self.saveState(100)
        # {'original': newfile}
        return self.new_render()

    def async_render(self, files={}):
        return self.new_render()

    def new_render(self, files={}):
        if TASKQUEUE_RENDERING:
            Task.Publish("medialib", "on_render", {"id": self.id, "name": self.name, "kind": self.kind}, channel="tq_app_handler_medialib")
        else:
            self.createRenditions()
        return True

    def createRenditions(self, files={}):
        self.saveState(101) #  rendering
        logger.info("create renditions, {}:{}".format(self.name, self.kind))
        render = __import__('medialib.render', globals(), locals(), ['render'])
        res = render.render(self, 1, files=files, log=logger.info)
        if not res:
            self.saveState(110)
            self._renderFailed(files)
        else:
            self.saveState(200)

    def _renderFailed(self, files):
        err = self.render_error
        if files:
            faildir = os.environ.get('TMPDIR', '/tmp') + "/validate_fail"
            try:
                os.mkdir(faildir)
            except OSError:
                pass
            for f in files:
                filename = faildir + "/" + str(int(time.time())) + "_" + f
                try:
                    outf = open(filename + ".dat", 'wb')
                    fp = files[f]
                    if hasattr(fp, "chunks"):
                        for chunk in fp.chunks():
                            outf.write(chunk)
                    else:
                        chunk = fp.read(1024)
                        while chunk:
                            outf.write(chunk)
                            chunk = fp.read(1024)
                    outf.close()
                    outf = open(filename + ".txt", 'w')
                    import pprint
                    outf.write(pprint.pformat(vars(files[f])))
                    outf.write(pprint.pformat(vars(self)))
                    outf.close()
                except OSError:
                    pass
        if self.state == 111:
            # ignore errors
            try:
                self.deleteRenditions()
            except Exception as err:
                logger.exception(err)
        raise Exception(err)

    def guessKind(self):
        filename = self.name
        if getattr(self, "newfile", None):
            filename = self.newfile.name
        if getattr(self, "base64_data", None):
            # base64 lets attempt to read the first few bytes
            kind = utils.guessBase64Kind(self.base64_data)
            if kind != None:
                self.ext = kind
                if kind in ["png", "jpg", "jpeg", "jfif", "bmp", "gif", "tif"]:
                    self.kind = "I"
                    return
        (mt, _) = mimetypes.guess_type(filename)
        if mt == None:
            self.kind = '*'
        elif mt[:6] == 'image/':
            self.kind = 'I'
        elif mt[:6] == 'video/':
            self.kind = 'V'
        elif mt == 'application/x-shockwave-flash':
            self.kind = 'V'
        else:
            self.kind = '*'

    def saveState(self, state):
        self.state = state
        return super(MediaItem, self).save()

    def save(self, *args, **kwargs):
        """
        When saving MediaItem set newfile attribute to upload new file and start rendering
        """
        # set state to render-pending if new upload
        has_fields = hasattr(self, 'newfile') or hasattr(self, 'newurl') or hasattr(self, 'downloadurl') or hasattr(self, 'base64_data')
        state = self.state
        if self.state is None or self.state >= 100 or has_fields:
            self.state = 100

        if not self.kind:
            self.guessKind()

        if self.kind and self.library and self.library.allowed_kinds and not self.kind in self.library.allowed_kinds:
            raise Exception("Invalid media type for this library")

        if not self.library:
            lib, created = MediaLibrary.objects.get_or_create(name="default", description="default", owner=User.objects.first())
            self.library = lib

        ret = super(MediaItem, self).save(*args, **kwargs)

        rkind = self.kind
        if rkind in ('A','S',):
            rkind = 'V'
        if hasattr(self, 'newfile'):
            newfile = self.newfile
            delattr(self, 'newfile')
            rendition = MediaItemRendition(mediaitem=self, name="Original", use='original', kind=rkind, is_original=True)
            rendition.upload(newfile)
            rendition.save()
            if self.state >= 100:
                if rkind == 'V':
                    self.async_render({'original': newfile})
                else:
                    self.new_render({'original': newfile})
        elif hasattr(self, 'base64_data'):
            fileName, ext = os.path.splitext(self.name)
            if hasattr(self, "ext"):
                ext = self.ext
            # print "media suffix: " + ext
            # print "media kind: " + self.kind
            newfile = tempfile.NamedTemporaryFile(suffix=ext)
            newfile.write(utils.fromBase64ToBytes(self.base64_data))
            newfile.seek(0)
            delattr(self, 'base64_data')
            rendition = MediaItemRendition(mediaitem=self, name="Original", use='original', kind="I", is_original=True)
            rendition.upload(newfile)
            rendition.save()
            if self.state >= 100:
                self.new_render({'original': newfile})
        elif hasattr(self, 'downloadurl'):
            # this needs to change to a background task via a stage of rendering
            # original should be the URL
            newurl = self.downloadurl
            delattr(self, 'downloadurl')
            res = urllib.request.urlopen(newurl)
            fileName, ext = os.path.splitext(newurl)
            newfile = tempfile.NamedTemporaryFile(suffix=ext)
            # newfile.name = self.name
            newfile.write(res.read())
            newfile.seek(0)
            rendition = MediaItemRendition(mediaitem=self, name="Original", use='original', kind=rkind, is_original=True)
            rendition.upload(newfile)
            rendition.save()
            rendition = MediaItemRendition(mediaitem=self, name="OriginalSource", use='source', url=newurl, bytes=0, kind=rkind)
            rendition.save()
            if self.state >= 100:
                self.new_render({'original': newfile})
        elif hasattr(self, 'newurl'):
            newurl = self.newurl
            delattr(self, 'newurl')
            rendition = MediaItemRendition(mediaitem=self, name="Original", use='original', url=newurl, bytes=0, kind=rkind, is_original=True)
            rendition.save()
            if hasattr(self, 'newurl_local'):
                meta = MediaMeta(rendition=rendition, key="url_local", value=self.newurl_local)
                meta.save()
            if self.state >= 100:
                self.new_render()
        return ret

    def video_rendition_list(self):
        return self.renditions.filter(Q(use='video')|Q(use="original")).order_by('width')

    def original(self):
        """
        Get original rendition
        """
        try:
            if self.kind == 'A':
                return self.renditions.exclude(kind='L').filter(is_original=True).order_by('created')[0]
            return self.renditions.filter(is_original=True).order_by('-created')[0]
        except IndexError:
            return None

    def still(self):
        """
        Get still rendition
        """
        if self.kind == 'I':
            return self.original()
        try:
            return self.renditions.filter(use='still').order_by('-created')[0]
        except IndexError:
            return MediaItemRendition(name="Preview not yet available", url="/static/img/noimage.gif", fake=True)

    def poster_url(self, request=None):
        return self.get('poster', 'still', 'original', 'noimage').view_url(request=request, expires=None)

    def get(self, *args):
        """
        Get first matching rendition
        """
        for use in args:
            if use == 'noimage':
                return MediaItemRendition(name="Rendition not yet available", url="/static/img/noimage.gif", fake=True)
            try:
                return self.renditions.filter(use=use).order_by('-created')[0]
            except IndexError:
                pass
        return None

    def thumbnail_animated(self):
        """
        Get animated thumbnail rendition
        """
        return self.renditions.filter(use='thumbnail-animated').order_by('-created').first()

    def isImage(self):
        org = self.original()
        if org is not None:
            return org.kind == "I"
        return False

    def isAnimated(self):
        org = self.original()
        if org is not None:
            return org.kind == "N"
        return False

    def animated_url(self):
        if self.kind == "V":
            thumb = self.thumbnail_animated()
            if thumb:
                return thumb.view_url_nonexpire()
        elif self.kind == "I":
            org = self.original()
            if org.kind == "N":
                return org.view_url_nonexpire()
        return None

    def image_small(self):
        """
        Get small tumbnail rendition
        """
        try:
            return self.renditions.filter(use='image', width__lt=200).order_by('-created')[0]
        except IndexError:
            pass
        try:
            return self.renditions.filter(use='image').order_by('-created')[0]
        except IndexError:
            pass
        return self.still()

    def thumbnail_url(self, width=320):
        thumb = self.renditions.filter(kind="I", use="thumbnail", width__lte=width).order_by('-width').first()
        if thumb:
            return thumb.view_url_nonexpire()
        return None

    def thumbnail_small(self):
        """
        Get small tumbnail rendition
        """
        try:
            return self.renditions.filter(use='thumbnail', width__lt=80).order_by('-created')[0]
        except IndexError:
            pass
        try:
            return self.renditions.filter(use='thumbnail').order_by('-created')[0]
        except IndexError:
            pass
        if self.kind == '*':
            return MediaItemRendition(name="Unknown Attachment", url="/static/img/unknown.gif", fake=True)
        return self.still()

    def thumbnail_large(self):
        """
        Get large thumbnail rendition
        """
        try:
            return self.renditions.filter(use='thumbnail', width__gte=80).order_by('-created')[0]
        except IndexError:
            pass
        try:
            return self.renditions.filter(use='thumbnail').order_by('-created')[0]
        except IndexError:
            pass
        if self.kind == '*':
            return MediaItemRendition(name="Unknown Attachment", url="/static/img/unknown.gif", fake=True)
        return self.still()

    def image_larger(self, size):
        """
        Get any image with width same or larger than <size>
        """
        try:
            return self.renditions.filter(use__in = ('thumbnail', 'image'), width__gte=size).order_by('width', '-created')[0]
        except IndexError:
            pass

        return self.still()

    def video_url(self, quality="480p", request=None):
        video = self.renditions.filter(kind="V", name=quality).order_by('-id').first()
        if video is None:
            video = self.original()
            if video is None:
                return None
        return video.view_url(request=request, expires=None)

    def image_url(self, request=None):
        image = self.renditions.filter(kind="I", use="thumbnail").order_by('-width').first()
        if image is None:
            image = self.original()
            if image is None:
                return None
        url = image.view_url(request=request, expires=None)
        if url and not url.startswith("http"):
            if url.startswith("/"):
                url = url[1:]
            return "{}{}".format(settings.BASE_URL_SECURE, url)
        return url

    def original_url(self, request=None):
        org = self.original()
        if org is not None:
            return org.view_url(request=request, expires=None)
        return self.url(request=request)

    def url(self, size=None, request=None):
        if self.kind == "V":
            return self.video_url(request=request)
        elif self.kind == "I":
            return self.image_url(request=request)
        org = self.original()
        if org is not None:
            return org.view_url(request=request, expires=None)
        return None

    def getImageRendition(self, width=640, name=None, use="thumbnail", request=None, flat=True):
        image = None
        if name is None:
            image = self.renditions.filter(kind="I", use=use, width__lte=width).order_by('-width').first()
        else:
            image = self.renditions.filter(kind="I", name=name).order_by('-width').first()
        if image is None:
            return None
        if not flat:
            return image
        return {
            "kind": image.kind,
            "content_type": mimetypes.guess_type(image.url)[0],
            "bytes":image.bytes,
            "url":image.view_url(request=request, expires=None, is_secure=True),
            "width":image.width,
            "height":image.height
        }

    def getVideoRendition(self, height=640, request=None, flat=True):
        video = self.renditions.filter(kind="V", use="video", height__lte=height).order_by('-height').first()
        if not flat:
            return video
        if video:
            return {
                "bytes":video.bytes,
                "url":video.view_url(request=request, expires=None, is_secure=False),
                "secure_url":video.view_url(request=request, expires=None, is_secure=True),
                "width":video.width,
                "height":video.height,
                "use":"video"
            }
        return None

    def getOriginalRendition(self, request=None):
        orig = self.original()
        if orig is None:
            return None
        return {
            "kind": orig.kind,
            "content_type": mimetypes.guess_type(self.name)[0],
            "bytes":orig.bytes,
            "url":orig.view_url(request=request, expires=None, is_secure=False),
            "secure_url":orig.view_url(request=request, expires=None, is_secure=True),
            "width":orig.width,
            "height":orig.height
        }

    def image_renditions(self, request=None):
        return {
            "square":self.getImageRendition(name="square thumbnail", request=request),
            "medium":self.getImageRendition(width=620, request=request),
            "large":self.getImageRendition(width=1020, request=request),
            "original":self.getOriginalRendition(request=request)
        }

    def remote_renditions(self, request=None):
        return {
            "websnap":self.getImageRendition(use="websnap", width=2000, request=request),
            "medium":self.getImageRendition(width=2000, request=request),
            "large":self.getImageRendition(width=2000, request=request),
            "original":self.getOriginalRendition(request=request)
        }

    def video_renditions(self, request=None):
        animated = self.thumbnail_animated()
        res = {
            "low":self.getVideoRendition(height=480, request=request),
            "medium":self.getVideoRendition(height=720, request=request),
            "high":self.getVideoRendition(height=1080, request=request),
            "original":self.getOriginalRendition(request=request)
        }
        if animated:
            res["animated"] = {
                "bytes":animated.bytes,
                "url":animated.view_url(request=request, expires=None, is_secure=True),
                "width":animated.width,
                "height":animated.height,
                "use":"gif"
            }
        poster = self.get('poster', 'still', 'original', 'noimage')
        if poster:
            res["poster"] = {
                "bytes":poster.bytes,
                "url":poster.view_url(request=request, expires=None, is_secure=True),
                "width":poster.width,
                "height":poster.height,
                "use":"poster"
            }
        thumb = self.getImageRendition(name="square thumbnail", request=request)
        if thumb:
            res["square_thumbnail"] = thumb

        thumb = self.getImageRendition(name="small thumbnail", request=request)
        if thumb:
            res["small_thumbnail"] = thumb

        thumb = self.getImageRendition(name="medium thumbnail", request=request)
        if thumb:
            res["large_thumbnail"] = thumb

        thumb = self.getImageRendition(name="video still", request=request)
        if thumb:
            res["video_still"] = thumb
        return res

    def smart_renditions(self, request=None):
        if self.kind == "I":
            return self.image_renditions(request=request)
        elif self.kind == "V":
            return self.video_renditions(request=request)
        elif self.kind == "E":
            return self.remote_renditions(request=request)
        return { "original": self.getOriginalRendition(request=request) }

    def duration(self):
        org = self.original()
        if org is not None:
            return org.get_meta('duration', 0.0, float)
        return 0.0

    def bytes(self):
        org = self.original()
        if org is not None:
            return org.bytes
        return 0

    def live_state_ingesting(self):
        return self.kind == 'L' and self.state > 100 and self.state < 110
    def live_state_available(self):
        return self.live_state_ingesting() or (self.state == 200)
    def live_ingest_url(self):
        try:
            return "/".join(self.original().url.split("/")[:-1])
        except AttributeError:
            return None
    def live_local_url(self):
        orig = self.original()
        if not orig:
            return None
        try:
            url = orig.mediameta_set.get(key='url_local').value
        except MediaMeta.DoesNotExist:
            url = orig.url

        try:
            return "/".join(url.split("/")[:-1])
        except AttributeError:
            return None
    def live_stream_id(self):
        try:
            return self.original().url.split("/")[-1]
        except AttributeError:
            return None

    def addRendtion(self, name, use, kind, url, width=0, height=0):
        #render = __import__('medialib.render', globals(), locals(), ['render'])
        rendition = MediaItemRendition(mediaitem=self, name=name,
            use=use, url=url,
            bytes=0, width=width, height=height,
            kind=kind, is_original=False)
        rendition.save()
        return rendition

    def deleteRenditions(self, keep_original=True):
        """
        Delete rendition (including stored file)
        """
        for r in self.renditions.all():
            if keep_original and r.use == "original":
                continue
            r.delete()

    def updateFromURL(self, url):
        url = url.strip()
        try:
            u = urllib.request.urlopen(url)
            if not u.code == 200:
                return None
        except IOError:
            return None

        self.deleteRenditions()
        self.state = 100
        res = urllib.request.urlopen(url)
        fileName, ext = os.path.splitext(url)
        newfile = tempfile.NamedTemporaryFile(suffix=ext)
        # newfile.name = self.name
        newfile.write(res.read())
        newfile.seek(0)
        rendition = MediaItemRendition(mediaitem=self, name="Original", use='original', kind=self.kind, is_original=True)
        rendition.upload(newfile)
        rendition.save()

        rendition = MediaItemRendition(mediaitem=self, name="OriginalSource", use='source', url=url, bytes=0, kind=self.kind, is_original=True)
        rendition.save()

        self.save()
        self.new_render({'original': newfile})

    @staticmethod
    def CreateFromURL(url, owner, library=None, kind=None):
        try:
            u = urllib.request.urlopen(url)
            if not u.code == 200:
                return None
        except IOError:
            return None

        filename = utils.getFileNameFromURL(url)
        if not kind:
            kind = utils.guessMediaKindByName(filename)

        # our first library should be our private library
        if not library:
            library = MediaLibrary.objects.filter(owner=owner).first()
            if not library:
                library = MediaLibrary(name='Default Library', owner=owner)
                library.save()

        media = MediaItem(library=library, name=filename, owner=owner, kind=kind, downloadurl=url)
        media.save()
        return media

class MediaItemMetaData(MetaDataBase):
    parent = models.ForeignKey(MediaItem, related_name="properties", on_delete=models.CASCADE)

class MediaItemRef(models.Model, RestModel):
    class RestMeta:
        GRAPHS = {
            "default": {
                "graphs":{
                    "media":"basic",
                    "generic__component":"basic",
                }
            },
            "list": {
                "graphs":{
                    "media":"basic",
                }
            },
            "simple": {
                "graphs":{
                    "media":"basic"
                }
            },
        }
    created = models.DateTimeField(auto_now_add=True, editable=False)
    media = models.ForeignKey(MediaItem, related_name="references", on_delete=models.CASCADE)
    component = models.CharField(max_length=200, blank=True, null=True, default=None, db_index=True)
    component_id = models.IntegerField(db_index=True)

class CuePoint(models.Model):
    """
    Cue points within media item
    """
    item = models.ForeignKey(MediaItem, on_delete=models.CASCADE)
    start = models.FloatField()
    end = models.FloatField(null=True, blank=True)
    subitem = models.ForeignKey(MediaItem, related_name="cueparent", on_delete=models.CASCADE)


class CuePointMeta(models.Model):
    """
    MetaData on MediaItemRendition
    """

    cue = models.ForeignKey(CuePoint, on_delete=models.CASCADE)
    key = models.CharField(max_length=127, db_index=True, help_text="Key")
    value = models.TextField(null=True, blank=True, help_text="Value")

    def __str__(self):
        return self.key

class MediaItemRendition(models.Model):
    """
    A rendition of a media item
    """

    mediaitem = models.ForeignKey(MediaItem, related_name='renditions', help_text="Item this rendition is for", on_delete=models.CASCADE)
    name = models.CharField(max_length=127, help_text="Name of rendition (copied from definition)")
    use = models.CharField(max_length=32, null=True, blank=True, help_text="The intended use for this media item (copied from definition)")
    rendition_definition = models.ForeignKey(RenditionDefinition, null=True, help_text="The rendition type that generated this rendition", on_delete=models.CASCADE)
    url = models.CharField(max_length=255, help_text="internal url for rendition")
    created = models.DateTimeField(auto_now_add=True, editable=False, help_text="When item was created")
    width = models.IntegerField(null=True, help_text="Width (if available)")
    height = models.IntegerField(null=True, help_text="Height (if available)")
    bytes = models.IntegerField(help_text="Size of rendition file")
    kind = models.CharField(max_length=1, choices=RenditionKinds, help_text="Kind of rendition")
    is_original = models.BooleanField(default=False, help_text="Whether is original of kind")

    @property
    def key(self):
        u = urlparse(self.url)
        return u.path.lstrip('/')

    def __init__(self, *args, **kwargs):
        self._fake = kwargs.pop('fake', False)
        super(MediaItemRendition, self).__init__(*args, **kwargs)

    def __bool__(self):
        return not self._fake

    def __str__(self):
        try:
            return str(self.mediaitem) + ": " + self.name
        except MediaItem.DoesNotExist:
            return self.name

    def ext(self):
        """
        File extension of rendition
        """
        try:
            ext = self.url.split('.')[-1]
            if '/' in ext: return ''
            return ext
        except IndexError:
            return ''

    def upload(self, fp, prefix=""):
        """
        Upload rendition to non-volatile storage
        """
        doclose = False
        if type(fp) == str:
            doclose = True
            fp = open(fp)

        paths = []
        paths.append(self.mediaitem.default_store())
        paths.append("/{}/".format(int_to_base36(self.mediaitem.pk)))
        path = "".join(paths)
        if self.rendition_definition != None:
            paths.append(int_to_base36(self.rendition_definition.pk))
        else:
            paths.append("0")
        paths.append("_")
        paths.append(utils.toMD5(path, int(time.time())))
        paths.append(".")
        ext = ".dat"
        if "." in fp.name:
            ext = fp.name.split('.')[-1]
        elif hasattr(self.mediaitem, "ext"):
            ext = self.mediaitem.ext
        paths.append(ext)
        # print(paths)
        self.url = "".join(paths)
        stores.upload(self.url, fp, background=True)
        try:
            self.bytes = fp.size
        except AttributeError:
            self.bytes = os.fstat(fp.fileno()).st_size

        if doclose:
            fp.close()
        else:
            try:
                if self.fp:
                    return
            except  AttributeError:
                pass
            self.fp = fp
            try:
                self.filename = fp.name
            except AttributeError:
                pass

    def view_url(self, expires=3600, request=None, is_secure=None):
        """
        Get the URL of rendition that can be used for viewing
        """
        if is_secure is None:
            is_secure = request and hasattr(request, 'is_secure') and request.is_secure()

        try:
            if self.rendition_definition.preset.short_name == "hls":
                url = "/medialib/hls/%d.%s/index.m3u8" % (self.pk, self.mediaitem.token())
                if not self.get_meta('final'):
                    url += "?live=1"
                return url
            elif self.use == "youtube":
                pre = "http"
                if is_secure:
                    pre = "https"
                return "{0}://youtu.be/{1}".format(pre, self.url)
        except ObjectDoesNotExist:
            pass
        except AttributeError:
            pass

        return stores.view_url(self.url, expires=expires, is_secure=is_secure, request=request)

    def view_url_nonexpire(self, request=None, is_secure=True):
        return self.view_url(expires=None, request=request, is_secure=is_secure);

    def rtmp_url(self, expires=3600, request=None):
        """
        Get the URL of rendition that can be used for viewing
        """
        try:
            if self.rendition_definition.preset.short_name == "hls":
                return None
        except ObjectDoesNotExist:
            pass
        except AttributeError:
            pass
        if request and hasattr(request, 'is_secure') and request.is_secure():
            is_secure = True
        else:
            is_secure = False
        return stores.rtmp_url(self.url, expires=expires, is_secure=is_secure, request=request)

    def get_local_url(self):
        """
        Get local url for rendition
        """
        try:
            if self.rendition_definition.preset.short_name == "hls":
                return "http://" + settings.HOSTNAME + "/medialib/hls/%d.%s/index.m3u8" % (self.pk, self.mediaitem.token())
        except ObjectDoesNotExist:
            pass
        except AttributeError:
            pass
        extra = ""
        if stores.type(self.url) == "rtmpstore":
            if self.mediaitem.kind == "L":
                extra = " live=1 buffer=200"
            else:
                extra = " buffer=1"
        try:
            return stores.view_url(self.mediameta_set.get(key='url_local').value) + extra
        except MediaMeta.DoesNotExist:
            return stores.view_url(self.url) + extra

    def check_file(self):
        """
        Check if file exists in backend
        """
        if self.kind == "E":
            return True

        if self.url[-1] == "/":
            raise Exception("check_file on directory")
        return stores.exists(self.url) != False

    def read_all(self):
        """
        read the rendition
        """
        return stores.get_file(self.url, fp)

    def get_file(self, fp=None):
        """
        Fetch the rendition into file
        """
        if self.url[-1] == "/":
            raise Exception("getfile on directory")
        if fp is None:
            fp = tempfile.NamedTemporaryFile(suffix=('.' + self.ext()), prefix="{0}_".format(self.id))
        stores.get_file(self.url, fp)
        fp.seek(0)
        return fp

    def delete(self):
        """
        Delete rendition (including stored file)
        """
        if self.url.startswith(self.mediaitem.default_store()):
            stores.delete(self.url)
        return super(MediaItemRendition, self).delete()

    def set_meta(self, key, value):
        (meta, _) = MediaMeta.objects.get_or_create(rendition=self, key=key)
        meta.value = value
        meta.save()
        return meta

    def get_meta(self, key, dflt=None, type=None):
        try:
            ret = self.mediameta_set.get(key=key).value
        except MediaMeta.DoesNotExist:
            ret = dflt
        if type:
            try:
                ret = type(ret)
            except ValueError:
                ret = dflt
        return ret

    def bitrate(self):
        rate = self.rendition_definition.getParameter('video_bitrate')
        if rate:
            return int(rate) * 1024
        if self.bytes:
            dur = self.get_meta('duration')
            if dur:
                return bytes / dur
        return None

    def updateFromURL(self, url):
        url = url.strip()
        try:
            u = urllib.request.urlopen(url)
            if not u.code == 200:
                return None
        except IOError:
            return None

        res = urllib.request.urlopen(url)
        fileName, ext = os.path.splitext(url)
        newfile = tempfile.NamedTemporaryFile(suffix=ext)
        # newfile.name = self.name
        newfile.write(res.read())
        newfile.seek(0)
        self.upload(newfile)
        self.save()
        # self.new_render({'original': newfile})


class MediaMeta(models.Model):
    """
    MetaData on MediaItemRendition
    """

    rendition = models.ForeignKey(MediaItemRendition, help_text="Rendition this metadata belongs to", on_delete=models.CASCADE)
    key = models.CharField(max_length=127, db_index=True, help_text="Key")
    value = models.TextField(null=True, blank=True, help_text="Value")

    def __str__(self):
        return self.key

def _next_priority():
    prios = RenderInstance.objects.all().order_by('-priority').values_list('priority', flat=True)[:1]
    if len(prios) == 0:
        return 100
    elif not prios[0]:
        return 100
    else:
        return prios[0] + 1

class RenderInstance(models.Model):
    """
    Rendering engine instances
    """

    instance_id = models.CharField(max_length=16, db_index=True, help_text="Rendering engine ID")
    state = models.CharField(max_length=1, db_index=True, choices=RenderingEngineStates, help_text="Current state of engine")
    started = models.DateTimeField(auto_now_add=True, editable=False, help_text="When rendering was started")
    last_checkin = models.DateTimeField(default=datetime.now, help_text="time instance last checked in")
    shutdown = models.DateTimeField(null=True, blank=True, help_text="Time of instance shutdown")
    priority = models.IntegerField(default=_next_priority, null=True, blank=True, help_text="Render instance priority")
    rendering = models.ForeignKey(MediaItem, null=True, blank=True, related_name='render_instance', help_text="Media item currently being rendered", on_delete=models.CASCADE)
    message = models.TextField(null=True, blank=True, help_text="Render message")

    def __str__(self):
        return self.instance_id

    def last_message(self):
        try:
            return self.message.strip().split('\n')[-1]
        except (IndexError, AttributeError):
            return ''

class RenditionSegment(models.Model):
    """
    Segment of media rendition
    """
    rendition = models.ForeignKey(MediaItemRendition, related_name='segments', help_text="Rendition this metadata belongs to", on_delete=models.CASCADE)
    segment = models.IntegerField(help_text="Segment number")
    start = models.FloatField(db_index=True, help_text="Start time offset")
    end = models.FloatField(db_index=True, help_text="End time offset")
    duration = models.FloatField(help_text="Segment duration")
    bytes = models.IntegerField(help_text="Segment size")
    url = models.CharField(max_length=255, help_text="internal url for rendition")

    def __str__(self):
        return "%s %d" % (self.rendition, self.segment)

class MediaItemParameterSetting(models.Model):
    """
    Key/Value parameter pairs per media item
    """
    class Meta:
        unique_together = (('item', 'parameter'),)
    item = models.ForeignKey(MediaItem, help_text="Media Item this pair belongs to", on_delete=models.CASCADE)
    parameter = models.ForeignKey(RenditionParameter, help_text="Parameter", on_delete=models.CASCADE)
    setting = models.CharField(max_length=127, null=True, blank=True, help_text="Value")

    def __str__(self):
        return "%s - %s" % (str(self.item), str(self.parameter))

