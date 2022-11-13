from ..exceptions import *
from ..render_utils import RenderProc
from . import video_getinfo

from django import db

from medialib import stores
from medialib.models import RenditionSegment

import os
import tempfile
import subprocess
import shutil
import glob
import signal
import sys
import errno

hls_cmd = ['streamsegmenter', "-s", "120", "-r", "3600"]

def sigusr(signum, frame):
    pass

def sigterm(proc):
    def sighand(signum, frame):
        try:
            proc.terminate()
        except OSError:
            pass

    return sighand

def _collect(tmpdir, url, rendition):
    while True:
        segments = glob.glob(os.path.join(tmpdir, "segment-*.ts"))
        if not segments:
            break
        segints = []
        for seg in segments:
            fn = os.path.split(seg)[-1]
            segnum = int(fn[8:-3])
            segints.append((segnum, seg))
        segints.sort()
        for (segnum, seg) in segints:
            fp = open(seg)
            segurl = url + str(segnum) + ".ts"
            stores.upload(segurl, fp)
            meta = video_getinfo.getinfo(seg)
            fsize = os.fstat(fp.fileno()).st_size
            rendition.bytes += fsize
            rendition.__class__.objects.filter(pk=rendition.pk).update(bytes=rendition.bytes)
            rseg = RenditionSegment(rendition=rendition, segment=segnum, start=meta['start'], duration=meta['duration'], end=meta['start']+meta['duration'], bytes=fsize, url=segurl)
            rseg.save()
            fp.close()
            rendition.set_meta("last_segment", segnum)
            os.unlink(seg)


def run(rendition, infile, params={}, extra_args=[], final_args=[]):
    cmd = list(hls_cmd)
    
    copy_params = (	('segment_duration', '-d'),
              )
    for p in copy_params:
        if p[0] in params:
            s = str(params[p[0]])
            if len(p) > 2:
                s = p[2] + s
            if len(p) > 3:
                s = s + p[3]
            cmd += [p[1], s]

    tmpdir = tempfile.mkdtemp()

    (rp, wp) = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.dup2(wp, sys.stdout.fileno())
        os.dup2(wp, sys.stderr.fileno())
        os.close(rp)
        os.close(wp)
        db.connection.close()
        pid = os.getpid()
        cmd += ["-p", str(pid)] + extra_args + final_args + [tmpdir, "segment", '']

        signal.signal(signal.SIGUSR1, sigusr)

        fd = os.open(infile, os.O_RDONLY)
        proc = subprocess.Popen(cmd, close_fds=True, stdin=fd)
        os.close(fd)
        signal.signal(signal.SIGTERM, sigterm(proc))

        rval = 250
        try:
            while True:
                try:
                    pid, sts = os.waitpid(proc.pid, 0)
                    if pid >= 0:
                        rval = os.WEXITSTATUS(sts)
                        break
                except OSError as err:
                    if err.errno == errno.EINTR:
                        _collect(tmpdir, rendition.url, rendition)
                        db.reset_queries()
                        continue
                    raise
                except:
                    raise
        finally:
            try:
                _collect(tmpdir, rendition.url, rendition)
            except:
                pass
            rendition.set_meta("final", "1")
            shutil.rmtree(tmpdir)
        os._exit(rval)
    else:
        os.close(wp)
        return RenderProc(pid, errfile=rp)

