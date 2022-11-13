from ..engines import ffmpeg
from ..render_utils import *
from ..exceptions import *

import random
import tempfile
import logging
import time
from PIL import Image
import os

from django.conf import settings

from rest.log import getLogger
logger = getLogger("medialib", filename="medialib.log")


PresetConfig = {
    'name':		'Video Still',
    'description':	'Still frame from video',
    'stage':	10,
    'default_use':	'still',
    'applicable_kinds': 'VLAS',
    'parameters': {
        'image_container': {
            'description':	'Output image container extension',
            'required':	True,
            'kind':		'C',
            'configurable':	True,
            'choices':	'gif,jpg,png',
            'value':	'jpg',
        },
        'pix_fmt': {
            'description':	'Pixel format',
            'required':	False,
            'kind':		'C',
            'configurable':	True,
            'choices':	'yuv420p,yuyv422,rgb24,bgr24,yuv422p,yuv444p,yuv410p,yuv411p,gray,monow,monob,yuvj420p,yuvj422p,yuvj444p,uyvy422,bgr8,bgr4,bgr4_byte,rgb8,rgb4,rgb4_byte,nv12,nv21,argb,rgba,abgr,bgra,gray16be,gray16le,yuv440p,yuvj440p,yuva420p,rgb48be,rgb48le,rgb565be,rgb565le,rgb555be,rgb555le,bgr565be,bgr565le,bgr555be,bgr555le,yuv420p16le,yuv420p16be,yuv422p16le,yuv422p16be,yuv444p16le,yuv444p16be,rgb444le,rgb444be,bgr444le,bgr444be,bgr48be,bgr48le,yuv420p9be,yuv420p9le,yuv420p10be,yuv420p10le,yuv422p10be,yuv422p10le,yuv444p9be,yuv444p9le,yuv444p10be,yuv444p10le,yuv422p9be,yuv422p9le',
            'value':	'yuvj420p',
        },
        'bucket_size': {
            'description':	'Histogram bucket size',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	32,
        },
        'bucket_max': {
            'description':	'Maximum histogram bucket size before frame is considered solid',
            'required':	True,
            'kind':		'F',
            'configurable':	True,
            'value':	0.7,
        },
        'seek_time': {
            'description':	'Seek from start (sec)',
            'required':	True,
            'kind':		'F',
            'configurable':	True,
            'value':	0.5,
        },
    },
}

def render(item, renditiondef, params):
    original = get_rendition(item, 'original')
    params['no_threads'] = True
    params['frame'] = 1
    
    trycnt = 0
    starttime = time.time()
    maxseek = original.get_meta('duration', 60, float)

    logger.info("starting video_still")
    ok = False
    while not ok:
        logger.info("starting video_still 1")
        try:
            fp = tempfile.NamedTemporaryFile(suffix=('.' + params.get('image_container', 'jpg')), prefix="t_still_")
            dstfile = fp.name

            rotate=original.get_meta('rotate')
            if rotate:
                params['rotate'] = rotate

            ffmpeg.run(dstfile, original.filename, params, ['-f', 'image2'])
            fp.flush()
            fp.seek(0)
            im = Image.open(dstfile)
            im = im.convert("L")
            hist = im.histogram()
            total = im.size[0] * im.size[1]
            bucket_size = params.get('bucket_size', 32)
            i = 0
            j = 0;
            buckets = [0]
            for h in hist:
                if i > bucket_size:
                    i = 0
                    j += 1
                    buckets.append(0)
                buckets[j] += h
                i += 1
            ok = True
            for h in buckets:
                if h > total * params.get('bucket_max', 0.7):
                    ok = False

            if time.time() - starttime > getattr(settings, 'MEDIALIB_STILL_MAX_RUNTIME', 15):
                ok = True

            logger.info("starting video_still 2")
            if ok:
                logger.info("new render for still position")
                new_rendition(item, renditiondef, fp, kind='I', width=im.size[0], height=im.size[1], meta={"still_position": params.get('seek_time', 0)})

            trycnt += 1
            params['seek_time'] = params.get('seek_time', 0) + (0.5 + random.random()) * trycnt

            if params['seek_time'] > maxseek:
                trycnt = 0
                params['seek_time'] = 0
                params['bucket_max'] = params.get('bucket_max', 0.7) + 0.1
        
        except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
            logger.error("video_still failed")
            try:
                fp.close()
            except:
                pass

            if trycnt == 0 or params.get('bucket_max', 0.7) > 1:
                raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)
            else:
                logger.error("EXCEPTION:(recovered) %s" % str(err))
                # no suitable image, try again
                trycnt = 0
                params['seek_time'] = 0
                params['bucket_max'] = params.get('bucket_max', 0.7) + 0.1
