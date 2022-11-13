from ..exceptions import *
from .. import schedule as sched

import os
import tempfile
import subprocess
import shutil
import traceback
from medialib import utils
from rest.log import getLogger
logger = getLogger("medialib", filename="medialib.log")


ffmpeg_cmd = ['ffmpeg', '-loglevel', 'warning', '-y', ]
ffmpeg_threads = ['-threads', '4', ]

scheduled = []
cleanup_run = []


def run_cmd(args, stdin=None):
    fp = tempfile.TemporaryFile()
    if not stdin:
        stdin = os.open("/dev/null", os.O_RDONLY)
    proc = subprocess.Popen(args, close_fds=True, stderr=fp.fileno(), stdout=fp.fileno(), stdin=stdin)
    os.close(stdin)
    return (proc, fp)

def check_cmd(proc, fp, cmd=None):
    retval = proc.wait()
    fp.flush()
    fp.seek(0)
    bufl = fp.readlines()
    fp.close()
    buf = ""
    for l in bufl:
        l = utils.toString(l)
        if (l.startswith("FFmpeg version ") or
            l.startswith("  built on ") or
            l.startswith("  configuration: ") or
            l.startswith("  lib")):
            pass
        else:
            buf += l
    if retval:
        raise CmdError(retval, buf, cmd=cmd)
    return retval

def _params_to_args(params={}, extra_args=[], infile=None):
    args = []
    
    if 'height' in params and 'width' in params and 'size' not in params:
        if (params['width'] % 2) != 0:
            params['width'] = params['width'] - 1
        if (params['height'] % 2) != 0:
            params['height'] = params['height'] - 1
        params['size'] = '%dx%d' % (params['width'], params['height'])
    copy_params_pre = (
            ('seek_time', '-ss'),
        )
    copy_params = (
            ('video_codec', '-vcodec'),
            ('video_profile', '-vpre'),
            ('video_bitrate', '-b:v', '', 'k'),
            ('audio_codec', '-acodec'),
            ('audio_bitrate', '-b:a', '', 'k'),
            ('audio_channels', '-ac'),
            ('audio_freq', '-ar'),
            ('size', '-s'),
            ('frame', '-vframes'),
            ('frame_rate', '-r'),
            ('key_frame', '-g'),
            ('duration', '-t'),
            ('subme', '-subq'),
            ('merange', '-me_range'),
            ('video_container', '-f'),
            ('pix_fmt', '-pix_fmt'),
        )
    # if not params.get('no_threads', False):
    #     args += ffmpeg_threads
    pass_thru = int(params.get("pass_thru", 0))
    if pass_thru == 1:
        logger.info("pass_thru ignoring params", params)
        # only allow height to pass through
        new_params = {}
        for key in ["size", "video_codec"]:
            if key in params:
                new_params[key] = params[key]
        params = new_params

    for p in copy_params_pre:
        if p[0] in params:
            if type(params[p[0]]) == float:
                s = "%.5f" % params[p[0]]
            else:
                s = str(params[p[0]])
            if len(p) > 2:
                s = p[2] + s
            if len(p) > 3:
                s = s + p[3]
            args += [p[1], s]
    if infile:
        args += ['-i', infile]

    rotate = int(params.get('rotate', '0'))
    if rotate == 90:
        args += ['-vf', 'transpose=1']
    elif rotate == 180:
        args += ['-vf', 'vflip,hflip']
    elif rotate == 270:
        args += ['-vf', 'transpose=2']

    for p in copy_params:
        if p[0] in params:
            if type(params[p[0]]) == float:
                s = "%.5f" % params[p[0]]
            else:
                s = str(params[p[0]])
            if len(p) > 2:
                s = p[2] + s
            if len(p) > 3:
                s = s + p[3]
            args += [p[1], s]

    args += extra_args
    return args

def run(outfile, infile, params={}, extra_args=[], final_args=[]):
    cmd = ffmpeg_cmd + []
    cmd += _params_to_args(params, extra_args, infile)
    npass = params.get('pass', 1)
    currpass = 1
    tmpdir = tempfile.mkdtemp()
    prevdir = os.getcwd()
    os.chdir(tmpdir)
    try:
        while currpass <= npass:
            if npass == 1:
                cmdx = cmd + final_args + [outfile]
            elif currpass < npass:
                cmdx = cmd + ['-pass', str(currpass), '-f', 'rawvideo', '/dev/null']
            else:
                cmdx = cmd + ['-pass', str(currpass), ] + final_args + [outfile]
            logger.info("ffmpeg command", cmdx)
            (proc, fd) = run_cmd(cmdx)
            check_cmd(proc, fd, cmd=cmdx)
            currpass += 1
    except Exception as e:
        try:
            os.unlink(outfile)
        except:
            pass
        os.chdir(prevdir)
        raise e
    finally:
        os.chdir(prevdir)
        shutil.rmtree(tmpdir)

    return outfile

def schedule(outfile, infile, params={}, extra_args=[], final_args=[], cleanup=None, data=None):
    global scheduled
    scheduled.append({
        'params': params,
        'input': infile,
        'outfile': outfile,
        'extra_args': extra_args,
        'final_args': final_args,
        'cleanup': cleanup,
        'data': data,
    })
    sched.register_run(schedule_run)
    sched.register_cleanup(schedule_cleanup)

def schedule_run():
    global scheduled
    global cleanup_run
    while scheduled:
        this_run = [scheduled.pop(0)]
        i = 0
        while i < len(scheduled):
            if scheduled[i]['input'] == this_run[0]['input']:
                this_run.append(scheduled.pop(i))
            else:
                i += 1
        infile = this_run[0]['input']
        no_threads = False
        for one in this_run:
            if one['params'].get('no_threads', False):
                no_threads = True
        one['no_threads'] = no_threads
        for one in this_run:
            cmd = ffmpeg_cmd + _params_to_args(one['params'], one['extra_args'], infile) + one['final_args'] + [ one['outfile'] ]

        (proc, fd) = run_cmd(cmd)
        cleanup_run.append((proc, fd, this_run, ))

def schedule_cleanup():
    global cleanup_run
    ex = []
    for (proc, fd, this_run) in cleanup_run:
        try:
            check_cmd(proc, fd)
        except Exception as e:
            tb = getattr(e, 'stack', None)
            if not tb:
                tb = "".join(traceback.format_stack(None, 6)[:-1])
            ex.append((__name__, e, tb))
        while this_run:
            one = this_run.pop()
            if one['cleanup']:
                try:
                    one['cleanup'](one['data'], bool(ex))
                except Exception as e:
                    tb = getattr(e, 'stack', None)
                    if not tb:
                        tb = "".join(traceback.format_stack(None, 6)[:-1])
                    ex.append((one['cleanup'].__module__, e, tb))

    cleanup_run = []

    if ex:
        msg = "\n".join(('%s: %s\n\tSTACK\t: %s' % (x[0], str(x[1]), x[2].strip().replace("\n", "\n\t\t: ")) for x in ex))
        raise RenderError(msg)

