from ..exceptions import *
from ..render_utils import RenderProc, PipeThread

from django import db

import select
import fcntl
import os
import sys

class RtmpSinkRun(PipeThread):
    def read(self, infd, outf):
        select.select((infd,), (), ())
        return os.read(infd, 10240)
    
    def write(self, data, infd, outf):
        return outf.write(data)
        
def run(url, fname):
    from .rtmp import rtmp
    (rp, wp) = os.pipe()
    pid = os.fork()

    if pid == 0:
        global tdata
        os.dup2(wp, sys.stdout.fileno())
        os.dup2(wp, sys.stderr.fileno())
        os.close(rp)
        os.close(wp)
        
        fd = os.open(fname, os.O_RDONLY)
        fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

        db.connection.close()

        out = rtmp.sink(str(url))

        RtmpSinkRun(fd, out, delay_error=True)

        out.close()
        os.close(fd)
        os._exit(0)
    else:
        os.close(wp)
        return RenderProc(pid, errfile=rp)

