from ..exceptions import *

import os
import tempfile
import subprocess
import shutil

mp4box_cmd = ['MP4Box', ]

def run_cmd(args):
    fp = tempfile.TemporaryFile()
    nfd = os.open("/dev/null", os.O_RDONLY)
    retval = subprocess.call(args, close_fds=True, stderr=fp.fileno(), stdout=fp.fileno(), stdin=nfd)
    os.close(nfd)
    fp.flush()
    fp.seek(0)
    bufl = fp.readlines()
    fp.close()
    buf = ""
    for l in bufl:
        if (l.startswith("Saving ") or
            l.startswith("ISO File Writing ")):
            pass
        else:
            buf += l
    if retval:
        raise CmdError(retval, buf, cmd=args)
    return retval

def run(outfile, infile, params={}, extra_args=[], final_args=[]):
    cmd = mp4box_cmd + ['-out', outfile, '-inter', params.get('interleaves', '500'), infile]

    try:
        run_cmd(cmd)
    except Exception as e:
        try:
            os.unlink(outfile)
        except:
            pass
        raise e
    return outfile
