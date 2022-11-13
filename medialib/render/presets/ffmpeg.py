from ..engines import ffmpeg
from ..engines import mp4box
from ..render_utils import *
from ..exceptions import *

import tempfile

PresetParameters =  {
    'audio_bitrate': {
        'description':	'Audio bitrate (kbps)',
        'required':	True,
        'kind':		'I',
        'configurable':	True,
    },
    'audio_channels': {
        'description':	'Audio channels',
        'required':	True,
        'kind':		'I',
        'configurable':	True,
    },
    'audio_freq': {
        'description':	'Audio frequency (hz)',
        'required':	True,
        'kind':		'I',
        'configurable':	True,
    },
    'video_bitrate': {
        'description':	'Video bitrate (kbps)',
        'required':	True,
        'kind':		'I',
        'configurable':	True,
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
    },
    'seek_time': {
        'description':	'Seek from start (sec)',
        'required':	True,
        'kind':		'F',
        'configurable':	True,
    },
    'pix_fmt': {
        'description':	'Pixel format',
        'required':	False,
        'kind':		'C',
        'configurable':	True,
        'choices':	'yuv420p,yuyv422,rgb24,bgr24,yuv422p,yuv444p,yuv410p,yuv411p,gray,monow,monob,yuvj420p,yuvj422p,yuvj444p,uyvy422,bgr8,bgr4,bgr4_byte,rgb8,rgb4,rgb4_byte,nv12,nv21,argb,rgba,abgr,bgra,gray16be,gray16le,yuv440p,yuvj440p,yuva420p,rgb48be,rgb48le,rgb565be,rgb565le,rgb555be,rgb555le,bgr565be,bgr565le,bgr555be,bgr555le,yuv420p16le,yuv420p16be,yuv422p16le,yuv422p16be,yuv444p16le,yuv444p16be,rgb444le,rgb444be,bgr444le,bgr444be,bgr48be,bgr48le,yuv420p9be,yuv420p9le,yuv420p10be,yuv420p10le,yuv422p10be,yuv422p10le,yuv444p9be,yuv444p9le,yuv444p10be,yuv444p10le,yuv422p9be,yuv422p9le',
        'value':	'yuv420p',
    },
    'key_frame': {
        'description':	'Key frame rate',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'duration': {
        'description':	'Duration',
        'required':	False,
        'kind':		'F',
        'configurable':	True,
    },
    'pass': {
        'description':	'Number of encoding passes',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
}

def render(item, renditiondef, params, cleanup=None, data=None):
    oname = params.get('stream_output')
    if not oname:
        fp = tempfile.NamedTemporaryFile(suffix=('.' + params.get('video_container', 'mp4')), prefix="t_ffmpeg_")
        oname = fp.name
        direct = False
    else:
        fp = None
        direct = True
    
    original = get_rendition(item, 'original')
    params['no_threads'] = False
    
    try:
        params = calc_size(params, original.width, original.height, rotate=original.get_meta('rotate'))
        
        if item.kind == 'L':
            ffmpeg.schedule(oname, original.filename, params, cleanup=cleanup, data=data)
        else:
            ffmpeg.run(oname, original.filename, params)

        # if fp and params.get('video_container', 'mp4') == 'mp4':
        # 	fp2 = tempfile.NamedTemporaryFile(suffix=('.' + params.get('video_container', 'mp4')), prefix="t_mp4box_")
        # 	mp4box.run(fp2.name, fp.name)
        # 	fp.close()
        # 	fp = fp2

        new_rendition(item, renditiondef, params.get('url') or fp or oname, kind='V', width=params.get('width', None), height=params.get('height', None), direct=direct)
    except (IOError, SyntaxError, ValueError, EOFError, AttributeError, IndexError, CmdError) as err:
        iserr = True
        raise RenderError('%s: %s' % (renditiondef.name, str(err)), stack=err, show_stack=True)
    else:
        iserr = False
    finally:
        if item.kind != 'L' and cleanup:
            cleanup(data, iserr)
        try:
            fp.close()
        except:
            pass
