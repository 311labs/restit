from .ffmpeg import render as vid_render
from ..engines import rtmpsink
from ..exceptions import *

import tempfile
import os

from django.conf import settings

PresetConfig = {
    'name':		'Akamai streaming',
    'description':	'Stream video to akamai',
    'stage':	192,
    'use':		'rtmp',
    'applicable_kinds': 'L',
    'parameters': {
        'endpoint_id': {
            'description':	'Endpoint ID',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
        },
        'encoder_id': {
            'description':	'Encoder ID string',
            'required':	False,
            'kind':		'S',
            'configurable':	True,
        },
        'account_id': {
            'description':	'Account ID',
            'required':	True,
            'kind':		'S',
            'configurable':	True,
        },
        'account_password': {
            'description':	'Account Password',
            'required':	True,
            'kind':		'S',
            'configurable':	True,
        },
        'stream_name': {
            'description':	'Output stream name',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
        },
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
        'frame_rate': {
            'description':	'Frame rate',
            'required':	True,
            'kind':		'I',
            'configurable':	True,
            'value':	30,
        },
        'key_frame': {
            'description':	'Key frame rate',
            'required':	False,
            'kind':		'I',
            'configurable':	True,
            'value':	25,
        },
    },
}

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
        raise CmdError(ret, data['proc'].err(), cmd='*rtmpsink')
    
def render(item, renditiondef, params):
    params['video_container'] = 'flv'
    params['video_codec'] = 'libx264'
    params['audio_codec'] = 'libfaac'
    if params.get('audio_bitrate') >= 96 and 'audio_channels' not in params:
        params['audio_channels'] = 2
    (fp, fname) = tempfile.mkstemp(prefix="t_akamai_")
    os.close(fp)
    os.unlink(fname)
    os.mkfifo(fname)

    proc = rtmpsink.run(
        'rtmp://%s%d%s conn=S:encoder:%s:%s live=true akUserId=%s akPass=%s playpath=%s@%d' %  (
            getattr(settings, 'AKAMAI_ENTRY_PREFIX', 'p.ep'),
            params['endpoint_id'],
            getattr(settings, 'AKAMAI_ENTRY_SUFFIX', '.i.akamaientrypoint.net/EntryPoint'),
            params.get('encoder_id', '0.0.0.0'),
            params['account_id'],
            params['account_id'],
            params['account_password'],
            params['stream_name'],
            params['endpoint_id'],
        ), fname)
    params['stream_output'] = fname

    params['url'] = 'rtmp://%s%s%s%s@%d' % (
        getattr(settings, 'AKAMAI_EDGE_PREFIX', 'cp'),
        params['account_id'],
        getattr(settings, 'AKAMAI_EDGE_SUFFIX', '.live.edgefcs.net/live/'),
        params['stream_name'],
        params['endpoint_id'],
    )

    return vid_render(item, renditiondef, params, cleanup=cleanup, data={'proc': proc, 'fname': fname})
