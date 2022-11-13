from ..exceptions import *
from ..render_utils import RenderProc, PipeThread

from django import db

import select
import fcntl
import os
import sys

class RtmpDumpRun(PipeThread):
    def __init__(self, *args, **kwargs):
        return super(RtmpDumpRun, self).__init__(*args, **kwargs)

    def __del__(self):
        os.close(self.args[1])
        super(RtmpDumpRun, self).__del__()

    def read(self, inf, outfd):
        data = inf.read(10240)
        return data

    def write(self, data, inf, outfd):
        return os.write(outfd, data)

def thread(url):
    from .rtmp import rtmp
    (rp, wp) = os.pipe()
    inf = rtmp.dump(str(url))
    RtmpDumpRun(inf, wp, daemon=True)
    return rp
