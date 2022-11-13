from . import ffmpeg
from .. import render_utils
import copy

PresetConfig = [{
    'name':		'MPEG4 Video',
    'short_name':	'mp4',
    'module_name':	'mp4',
    'description':	'MPEG4 x264/AAC video',
    'stage':	190,
    'default_use':	'video',
    'applicable_kinds': 'VLAS',
    'parameters': {
    },
}]
PresetConfig[0]['parameters'].update(copy.deepcopy(ffmpeg.PresetParameters))
PresetConfig[0]['parameters'].update(copy.deepcopy(render_utils.PresetParameters))
render_utils.update_params(PresetConfig[0], 
    audio_bitrate=128,
    audio_channels= 2,
    audio_freq= 44100,
    video_bitrate= 512,
    frame_rate= 30,
    key_frame=25,
    __pass= 2,
)

PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[1].update({
    'name':		'MPEG4 Video (720p)',
    'short_name':	'mp4_hq',
    'module_name':	'mp4',
    'description':	'MPEG4 x264/AAC video (720p)',
})
render_utils.update_params(PresetConfig[1],
    frame_rate= 25,
    video_bitrate= 1200,
    audio_bitrate=168,
    height=720,
    key_frame=16,
)


PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[2].update({
    'name':		'MPEG4 Video (480p)',
    'short_name':	'mp4_mq',
    'module_name':	'mp4',
    'description':	'MPEG4 x264/AAC video (360p)',
})
render_utils.update_params(PresetConfig[2],
    frame_rate= 25,
    video_bitrate= 512,
    audio_bitrate=96,
    height=480,
    key_frame=25,
)

PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[3].update({
    'name':		'MPEG4 Video (360p)',
    'short_name':	'mp4_lq',
    'module_name':	'mp4',
    'description':	'MPEG4 x264/AAC video (360p)',
})
render_utils.update_params(PresetConfig[3],
    frame_rate= 15,
    video_bitrate= 128,
    audio_bitrate=40,
    height=360,
    key_frame=30,
)

PresetConfig.append(copy.deepcopy(PresetConfig[0]))
PresetConfig[4].update({
    'name':     'MPEG4 Video (1080p)',
    'short_name':   'mp4_hd',
    'module_name':  'mp4',
    'description':  'MPEG4 x264/AAC video (1080p)',
})
render_utils.update_params(PresetConfig[3],
    frame_rate= 50,
    video_bitrate= 1200,
    audio_bitrate=168,
    height=1080,
    key_frame=16,
)


def render(item, renditiondef, params):
    params['video_codec'] = 'libx264'
    params['audio_codec'] = 'aac'
    if params.get('audio_bitrate') >= 96 and 'audio_channels' not in params:
        params['audio_channels'] = 2
    return ffmpeg.render(item, renditiondef, params)
