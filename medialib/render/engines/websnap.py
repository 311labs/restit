from ..exceptions import *

import os
import tempfile
import subprocess

websnap_cmd = [ '/opt/phantomjs/bin/phantomjs', '/opt/phantomjs/webtopng.js' ]

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
        buf += l
    if retval:
        raise CmdError(retval, buf, cmd=args)
    return retval

def run(outfile, web_url):
    cmd = websnap_cmd + [web_url, outfile]
    try:
        run_cmd(cmd)
    except Exception as e:
        try:
            os.unlink(outfile)
        except:
            pass
        raise e
    return outfile
