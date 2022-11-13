from ..engines import ffmpeg, anigif
from ..render_utils import *
from ..exceptions import *
from .. import render_utils

import os
import shutil
import tempfile
import glob
import time
import copy
from PIL import Image

PresetConfig = {
    'name':		'Animated Thumbnail',
    'description':	'Animated GIF Thumbnail',
    'stage':	101,
    'use':		'thumbnail-animated',
    'applicable_kinds': 'VLAS',
    'parameters': {
        'frame': {
            'description':	'Number of frames to encode',
            'required':	False,
            'kind':		'I',
            'configurable':	True,
        },
        'frame_rate': {
            'description':	'Frame rate',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	4,
        },
        'seek_time': {
            'description':	'Seek from start (sec)',
            'required':	True,
            'kind':		'F',
            'configurable':	True,
        },
        'duration': {
            'description':	'Duration',
            'required':	False,
            'kind':		'F',
            'configurable':	True,
        },
    },
}
PresetConfig['parameters'].update(copy.deepcopy(render_utils.PresetParameters))

def render(item, renditiondef, params):
    fp = tempfile.NamedTemporaryFile(suffix=('.' + params.get('image_container', 'gif')), prefix="t_anigif_")
    dstfile = fp.name
    tmpdir = tempfile.mkdtemp()
    prevdir = os.getcwd()
    os.chdir(tmpdir)
    
    params['pass'] = 1

    original = get_rendition(item, 'original')
    params['no_threads'] = True
    if not 'frame' in params:
        params['frame'] = 20
    
    try:
        ffmpeg_params = params.copy()
        try:
            delattr(ffmpeg_params, 'width')
        except AttributeError:
            pass
        try:
            delattr(ffmpeg_params, 'height')
        except AttributeError:
            pass
        owidth = original.width
        oheight = original.height
        rotate=original.get_meta('rotate')
        if rotate:
            ffmpeg_params['rotate'] = rotate
            if rotate == 90 or rotate == 270:
                x = oheight
                oheight = owidth
                owidth = x
        ffmpeg.run(tmpdir + "/animate_%06d.png", original.filename, ffmpeg_params)

        params = calc_size(params, owidth, oheight)

        afiles = glob.glob(tmpdir + "/animate_*.png")
        afiles.sort()
        
        images = []
        for inf in afiles:
            im = Image.open(inf)

            if 'crop' in params:
                im = im.crop(params['crop'])
            if 'width' in params and 'height' in params:
                im.thumbnail((params['width'], params['height']))
        
            images.append(im)

        durations = [0.01] * len(afiles)
        durations[-1] = 1
        anigif.run(fp, images, durations, 0)

        new_rendition(item, renditiondef, fp, kind='N', width=params.get('width', None), height=params.get('height', None))
    except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
        os.chdir(prevdir)
        raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)
    finally:
        os.chdir(prevdir)
        shutil.rmtree(tmpdir)



