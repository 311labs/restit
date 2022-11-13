from ..exceptions import *

import os
import tempfile
import subprocess
import re
from medialib import utils


ffmpeg_cmd = ['ffmpeg']
ffmpeg_args = []
ffmpeg_args_url = []
ffmpeg_args_file = ['-vcodec', 'copy', '-acodec', 'copy', '-f', 'null', '/dev/null']

def getinfo(infile, params={}):
    fp = tempfile.TemporaryFile()
    nfd = os.open("/dev/null", os.O_RDONLY)
    if params.get('quick', False) or re.match(r'[^/]+://', infile):
        retval = subprocess.call(ffmpeg_cmd + ['-i', infile] + ffmpeg_args + ffmpeg_args_url, close_fds=True, stderr=fp.fileno(), stdout=fp.fileno(), stdin=nfd)
    else:
        retval = subprocess.call(ffmpeg_cmd + ['-i', infile] + ffmpeg_args + ffmpeg_args_file, close_fds=True, stderr=fp.fileno(), stdout=fp.fileno(), stdin=nfd)
    os.close(nfd)
    fp.flush()
    fp.seek(0)
    bufl = fp.readlines()
    fp.close()
    is_input = False

    meta = {}

    for l0 in bufl:
      for l in l0.split(b"\r"):
        l = utils.toString(l)
        if re.search(r'^Input ', l):
            is_input = True
        if re.search(r'^Output ', l):
            is_input = False

        if is_input:
            m = re.search(r'Duration: ([0-9]+):([0-9]+):([0-9]+)\.([0-9]+)', l)
            if m:
                meta['meta_duration'] = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + float("0." + m.group(4))

            m = re.search(r'Duration: .*, start: ([0-9.]+)', l)
            if m:
                meta['start'] = float(m.group(1))

            m = re.search(r'Stream.*Video:.* ([0-9]+)x([0-9]+)', l)
            if m:
                meta['width'] = int(m.group(1))
                meta['height'] = int(m.group(2))

            m = re.search(r'Stream.*Video:.* bitrate: ([^,]+)', l)
            if m:
                meta['video_bitrate'] = m.group(1)

            m = re.search(r'Stream.*Video: ([^,]+)', l)
            if m:
                meta['video_codec'] = m.group(1)

            m = re.search(r'Stream.*Video:.* ([0-9]+) tbc', l)
            if m:
                meta['frame_rate'] = m.group(1)

            m = re.search(r'Stream.*Audio:.* ([0-9]+) channels', l)
            if m:
                meta['audio_channels'] = int(m.group(1))

            m = re.search(r'Stream.*Audio:.* stereo', l)
            if m:
                meta['audio_channels'] = 2

            m = re.search(r'Stream.*Audio:.* mono', l)
            if m:
                meta['audio_channels'] = 1

            m = re.search(r'Stream.*Audio:.* Hz, ([0-9]+)\.([0-9]+),', l)
            if m:
                meta['audio_channels'] = int(m.group(1)) + int(m.group(2))

            m = re.search(r'Stream.*Audio:.* bitrate: ([^,]+)', l)
            if m:
                meta['audio_bitrate'] = m.group(1)

            m = re.search(r'Stream.*Audio: ([^,]+)', l)
            if m:
                meta['audio_codec'] = m.group(1)

            m = re.search(r'rotate *: ([0-9]+)', l)
            if m:
                meta['rotate'] = m.group(1)

        m = re.search(r' time=([0-9]+):([0-9]+):([0-9]+)\.([0-9]+) ', l)
        if m:
            meta['duration'] = int(m.group(1))*3600 + int(m.group(2))*60 + int(m.group(3)) + float("0." + m.group(4))

        m = re.search(r' time=([0-9]+)\.([0-9]+) ', l)
        if m:
            meta['duration'] = int(m.group(1)) + float("0." + m.group(2))


    if 'meta_duration' in meta and not 'duration' in meta:
        meta['duration'] = meta['meta_duration']

    return meta
