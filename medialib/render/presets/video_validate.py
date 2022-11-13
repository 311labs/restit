from ..engines import video_getinfo
from ..render_utils import *
from ..exceptions import *

import os
import subprocess
import tempfile

PresetConfig = {
    'name':		'Validate Video',
    'description':	'Basic video validation',
    'stage':	1,
    'default_use':	'validate',
    'applicable_kinds': 'V',
    'parameters': {
        'min_duration': {
            'description':	'Minimum video duration',
            'required':	False,
            'kind':		'F',
            'configurable':	True,
        },
        'max_duration': {
            'description':	'Maximum video duration',
            'required':	False,
            'kind':		'F',
            'configurable':	True,
        },
    },
}

def render(item, renditiondef, params):
    original = get_rendition(item, 'original')

    min_duration = params.get('min_duration', 0)
    max_duration = params.get('max_duration', 0)

    if min_duration < 60:
        min_duration_str = "%d seconds" % (min_duration)
    elif min_duration < 3600:
        if min_duration % 60 >= 55:
            min_duration_str = "%d minutes" % (min_duration/60 + 1)
        elif min_duration % 60 < 1:
            min_duration_str = "%d minutes" % (min_duration/60)
        else:
            min_duration_str = "%d minutes %d seconds" % (min_duration/60, min_duration%60)
    else:
        if min_duration % 3600 >= 3300:
            min_duration_str = "%d hours" % (min_duration/60 + 1)
        elif min_duration % 3600 < 60:
            min_duration_str = "%d hours" % (min_duration/60)
        else:
            min_duration_str = "%d hours %d minutes" % (min_duration/3600, min_duration%3600)

    if max_duration < 60:
        max_duration_str = "%d seconds" % (max_duration)
    elif max_duration < 3600:
        if max_duration % 60 < 5:
            max_duration_str = "%d minutes" % (max_duration/60)
        else:
            max_duration_str = "%d minutes %d seconds" % (max_duration/60, max_duration%60)
    else:
        if max_duration % 3600 < 300:
            max_duration_str = "%d hours" % (max_duration/60)
        else:
            max_duration_str = "%d hours %d minutes" % (max_duration/3600, max_duration%3600)

    meta = video_getinfo.getinfo(original.filename, params)
    if not (meta and ('duration' in meta or 'height' in meta)):
        raise ValidateError("Cannot decode uploaded file")
    if 'duration' in meta and min_duration and meta.get('duration', 0) < min_duration:
        raise ValidateError("Videos must be longer than {0} seconds and is {1}".format(min_duration, meta.get('duration', 0)))
    if 'duration' in meta and max_duration and meta.get('duration', 0) > max_duration:
        raise ValidateError("Videos must be shorter than {0} minutes".format(max_duration/60))
    if meta.get('video_codec', "").startswith("Apple ProRes 422"):
        raise ValidateError("Apple ProRes codec is currently not supported.  Please re-encode your video.")
    if meta.get('audio_channels', 2) > 2:
        raise ValidateError("Maximum of 2 audio channels allowed.")

    if 'height' in meta:
        original.height = meta.pop('height')
    if 'width' in meta:
        original.width = meta.pop('width')
    
    save_meta(original, meta)
    original.save()
