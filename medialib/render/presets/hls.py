from ..engines import ffmpeg
from ..engines import hls
from ..render_utils import *
from ..exceptions import *
from .. import render_utils
from medialib.models import RenditionSegment

from django.utils.http import base36_to_int, int_to_base36

import time
import hashlib
import tempfile
import os
import copy

from django.conf import settings

PresetConfig = {
    'name':		'HLS Video',
    'description':	'HLS x264/AAC video',
    'stage':	100,
    'use':		'video',
    'applicable_kinds': 'VLAS',
    'parameters': {
        'audio_bitrate': {
            'description':	'Audio bitrate (kbps)',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	128,
        },
        'audio_channels': {
            'description':	'Audio channels',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	2,
        },
        'audio_freq': {
            'description':	'Audio frequency (hz)',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	44100,
        },
        'video_bitrate': {
            'description':	'Video bitrate (kbps)',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	512,
        },
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
            'value':	30,
        },
        'seek_time': {
            'description':	'Seek from start (sec)',
            'required':	True,
            'kind':		'F',
            'configurable':	True,
        },
        'key_frame': {
            'description':	'Key frame rate',
            'required':	False,
            'kind':		'I',
            'configurable':	True,
            'value':	25,
        },
        'duration': {
            'description':	'Duration',
            'required':	False,
            'kind':		'F',
            'configurable':	True,
        },
        'segment_duration': {
            'description':	'Duration of individual HLS segments (sec)',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	3,
        },
    },
}
PresetConfig['parameters'].update(copy.deepcopy(render_utils.PresetParameters))


def hls_default(rendition):
    path = '/' + int_to_base36(rendition.mediaitem.pk) + '/' + (rendition.rendition_definition and int_to_base36(rendition.rendition_definition.pk) or "H")
    path += hashlib.md5(path + str(int(time.time()))).hexdigest()
    url = rendition.mediaitem.library.default_store() + path + "/"
    rendition.url = url
    rendition.bytes = 0
    return rendition

def subcue(item, renditiondef, params):
    try:
        cue = item.cueparent.all()[0]
    except IndexError:
        raise RenderError("Invalid cueparent")
        
    original = get_rendition(cue.item, 'hls')
    if not original:
        raise RenderError("hls rendition not enable in parent media")
    
    params = calc_size(params, original.width, original.height)
    rendition = hls_default(new_rendition(item, renditiondef, None, kind='V', width=params.get('width', None), height=params.get('height', None)))
    rendition.save()
    sdurr = original.get_meta('segment_duration')
    if sdurr:
        rendition.set_meta('segment_duration', sdurr)

    first = None
    try:
        first = original.segments.get(end__gte = cue.start, start__lte = cue.start)
    except RenderSegment.DoesNotExist:
        for seg in original.segments.all().order_by('start'):
            if seg.start > cue.start:
                first = seg
                break
    if not first:
        raise RenderError("Cue points out of range")
    if first.start >= cue.start - 2:
        cstart = first.start
    else:
        # XXX: break out first segment here
        cstart = first.start
    n = 1
    for seg in original.segments.filter(start__gte = cstart, start__lt = cue.end):
        RenditionSegment(rendition=rendition, segment=n, start=seg.start - cstart, end = seg.end - cstart, duration=seg.duration, bytes=seg.bytes, url=seg.url).save()
        n += 1

def cleanup(data, haserr):
    if haserr:
        ret = data['proc'].wait(nohang=True)
        if ret == None:
            data['proc'].kill()
            data['proc'].wait()
        elif ret == 0:
            ret = -1
    else:
        ret = data['proc'].wait()
    try:
        os.unlink(data['fname'])
    except:
        pass
    if ret:
        raise CmdError(ret, data['proc'].err(), cmd='*hls_segment')

def render(item, renditiondef, params):
    if item.kind == 'S': return subcue(item, renditiondef, params)
    proc = None
    (fp, fname) = tempfile.mkstemp(prefix="t_hls_")
    os.close(fp)
    os.unlink(fname)
    os.mkfifo(fname)

    original = get_rendition(item, 'original')
    params['no_threads'] = False
    params = calc_size(params, original.width, original.height, rotate=original.get_meta('rotate'))
    
    try:
        rendition = hls_default(new_rendition(item, renditiondef, None, width=params.get('width', None), height=params.get('height', None)))
        rendition.save()
        if 'segment_duration' in params:
            rendition.set_meta('segment_duration', params['segment_duration'])

        proc = hls.run(rendition, fname, params)
        ffmpeg_params = params.copy()
        ffmpeg_params['video_codec'] = 'libx264'
        ffmpeg_params['audio_codec'] = 'aac'
        ffmpeg_params['audio_channels'] = 2
        extra_args=('-f', 'mpegts', '-vbsf', 'h264_mp4toannexb', '-async' ,'1' ,'-adrift_threshold' ,'0',)
        if item.kind == 'L':
            ffmpeg.schedule(fname, original.filename, ffmpeg_params, extra_args=extra_args, data={'proc': proc, 'fname': fname}, cleanup=cleanup)
        else:
            ffmpeg.run(fname, original.filename, ffmpeg_params, extra_args=extra_args)
            proc.wait()
            proc = None

    except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
        raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)
    finally:
        if item.kind != 'L':
            if proc:
                proc.kill()
            try:
                os.unlink(fname)
            except:
                pass
        
