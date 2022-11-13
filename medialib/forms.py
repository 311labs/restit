from django.forms import ModelForm
from django import forms
from .models import *
from .utils import *

class MediaLibraryForm(ModelForm):
    class Meta:
        model = MediaLibrary
        fields = ('name', 'description', 'allowed_kinds')

class MediaItemForm(ModelForm):
    class Meta:
        model = MediaItem
        fields = ('name', 'description')

    def __init__(self, *args, **kwargs):
        if 'library' in kwargs:
            self._library = kwargs.pop('library')
        if 'kind' in kwargs:
            self._kind = kwargs.pop('kind')
        if 'state' in kwargs:
            self._state = kwargs.pop('state')
        return super(MediaItemForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        ret = super(MediaItemForm, self).save(commit=False)
        
        if hasattr(self, "_library"):
            ret.library = self._library
        if hasattr(self, "_kind"):
            ret.kind = self._kind
        if hasattr(self, "_state"):
            ret.state = self._state

        if commit:
            ret.save()
        return ret

class MediaItemUploadForm(MediaItemForm):
    file = forms.FileField()

    def clean_file(self):
        if not 'file' in self.files:
            return None
        self._upload_kind = validate_upload(self.files['file'])
        return self.files['file']

    def save(self, commit=True):
        ret = super(MediaItemUploadForm, self).save(commit=False)
        if 'file' in self.files:
            ret.kind = self._upload_kind
            ret.newfile = self.files['file']
        try:
            ret.owner
        except User.DoesNotExist:
            ret.owner = self.data['__request'].user
        
        if commit:
            ret.save()
        return ret

class MediaItemCanUploadForm(MediaItemUploadForm):
    file = forms.FileField(required=False)

class MediaItemNewLiveForm(MediaItemForm):
    def __init__(self, *args, **kwargs):
        self._url = kwargs.pop('url')
        if 'url_local' in kwargs:
            self._url_local = kwargs.pop('url_local')
        return super(MediaItemNewLiveForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        ret = super(MediaItemNewLiveForm, self).save(commit=False)
        ret.kind = 'L'
        ret.owner = self.data['__request'].user
        ret.newurl = self._url
        if hasattr(self, '_url_local'):
            ret.newurl_local = self._url_local
        if commit:
            ret.save()
        return ret

class RenditionSetForm(ModelForm):
    class Meta:
        model = RenditionSet
        fields = ('name', )

class RenditionDefinitionForm(ModelForm):
    class Meta:
        model = RenditionDefinition
        fields = ('name', 'description', 'use', 'active',)

    preset_name = forms.CharField(max_length=256, required=True)
    
    def __init__(self, *args, **kwargs):
        ret = super(RenditionDefinitionForm, self).__init__(*args, **kwargs)
        try:
            preset = getattr(getattr(self, 'instance', None), 'preset', None)
            if preset and preset.name:
                self.initial['preset_name'] = preset.name
        except RenditionPreset.DoesNotExist:
            pass
    
    def clean_preset_name(self):
        preset = RenditionPreset.objects.filter(short_name = self.cleaned_data['preset_name'])
        if not preset.count() == 1:
            preset = RenditionPreset.objects.filter(name = self.cleaned_data['preset_name'])
        if not preset.count() == 1:
            raise ValidationError('Invalid preset name')

        return preset[0]
    
    def save(self, commit=True):
        rend = super(RenditionDefinitionForm, self).save(commit=False)
        rend.preset = self.cleaned_data['preset_name']
        if commit:
            rend.save()
        return rend
        
class CuePointForm(ModelForm):
    class Meta:
        model = CuePoint
        fields = ('start', 'end')
    name = forms.CharField(max_length=127, required=True)
    description = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item')
        ret = super(CuePointForm, self).__init__(*args, **kwargs)

    def clean_start(self):
        if 'start' in self.cleaned_data:
            return self.cleaned_data['start']
        if self.item.kind == 'L':
            orig = self.item.original()
            if not orig:
                return 0
            return orig.get_meta('duration', 0)
        else:
            return 0
    def clean(self):
        if 'end' in self.cleaned_data and self.cleaned_data['start'] > self.cleaned_data['end']:
            raise forms.ValidationError("Cue end must be greater than start")
        return self.cleaned_data

    def save(self, commit=True):
        cue = super(CuePointForm, self).save(commit=False)
        try:
            cue.item
        except MediaItem.DoesNotExist:
            cue.item = self.item

        try:
            cue.subitem
        except MediaItem.DoesNotExist:
            subitem = MediaItem(library=cue.item.library,
                owner=cue.item.owner,
                name=self.cleaned_data.get('name', None),
                description=self.cleaned_data.get('description', None),
                kind='S',
                state=100,
            )
            subitem.save()
            cue.subitem = subitem
        if commit:
            cue.save()
            cue.subitem.new_render()
        return cue
