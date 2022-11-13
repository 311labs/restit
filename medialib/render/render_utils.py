
from django.apps import apps
from django.core.files.uploadedfile import *
from django.core.exceptions import ObjectDoesNotExist

import os
import tempfile
import string
import errno
from threading import Thread, Lock, Event

PresetParameters = {
    'width': {
        'description':	'Explicit width',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'height': {
        'description':	'Explicit height',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'maxwidth': {
        'description':	'Maximum width',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'maxheight': {
        'description':	'Maximum height',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'minwidth': {
        'description':	'Minimum width',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'minheight': {
        'description':	'Minimum height',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'maxaspect': {
        'description':	'Maximum aspect ratio (either direction)',
        'required':	False,
        'kind':		'F',
        'configurable':	True,
    },
    'aspect': {
        'description':	'Explicit aspect ratio',
        'required':	False,
        'kind':		'F',
        'configurable':	True,
    },
    'crop_x1': {
        'description':	'Crop left from top left',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'crop_y1': {
        'description':	'Crop top from top left',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'crop_x2': {
        'description':	'Crop right from top left',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
    'crop_y2': {
        'description':	'Crop bottom frop top left',
        'required':	False,
        'kind':		'I',
        'configurable':	True,
    },
}

def update_params(config, **kwargs):
    for p in kwargs:
        pn = p
        if pn[:2] == '__':
            pn = pn[2:]
        config['parameters'][pn]['value'] = kwargs[p]

class PipeThread(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.done = False
        self.exit = False
        try:
            self.delay_error = kwargs.pop('delay_error')
        except KeyError:
            self.delay_error = False
        try:
            self.daemon = kwargs.pop('daemon')
        except KeyError:
            self.daemon = False

        self.error = None
        self.tdata = ""
        self.tdata_lock = Lock()
        self.tdata_event = Event()

        self.write_t = Thread(target=self.writer)
        self.write_t.daemon = True
        self.write_t.start()

        if self.daemon:
            self.read_t = Thread(target=self.reader)
            self.read_t.daemon = True
            self.read_t.start()
        else:
            self.reader()
        if self.error:
            raise self.error

    def __del__(self):
        self.exit = True
        try:
            if self.read_t:
                self.read_t.join()
                self.read_t = None
        except:
            pass
        try:
            if self.write_t:
                self.write_t.join()
                self.write_t = None
        except:
            pass

    def wait(self, nohang=False):
        if self.daemon:
            if nohang:
                if self.read_t.is_alive():
                    return None

            self.read_t.join()
            if self.error:
                return -1
            return 0

    def kill(self):
        self.exit = True

    def writer(self):
        while True:
            self.tdata_event.wait()
            self.tdata_event.clear()
            if self.exit:
                return
            done = self.done
            with self.tdata_lock:
                data = self.tdata
                self.tdata = ""

            try:
                if data and not self.error:
                    self.write(data, *self.args, **self.kwargs)
            except Exception as e:
                self.error = e
                if not self.delay_error:
                    raise(e)
            if done or self.exit:
                return

    def reader(self):
        while True:
            data = self.read(*self.args, **self.kwargs)
            if self.exit or len(data) == 0:
                self.done = True
                if self.write_t:
                    self.tdata_event.set()
                    self.write_t.join()
                    self.write_t = None
                return

            with self.tdata_lock:
                self.tdata += data
            self.tdata_event.set()

class RenderProc:
    def __init__(self, pid, errfile=None):
        self.pid = pid
        self._errout = ""
        self._errlock = None
        if errfile:
            self.errread(errfile)

    def wait(self, nohang=False):
        opt = 0
        if nohang:
            opt |= os.WNOHANG
        while True:
            try:
                pid, sts = os.waitpid(self.pid, opt)
                if pid >= 0:
                    break
            except OSError as err:
                if err.errno == errno.EINTR:
                    if nohang:
                        return None
                    continue
                raise
        return os.WEXITSTATUS(sts)

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGTERM)
        except OSError:
            pass

    @staticmethod
    def mkfifo():
        (fp, fname) = tempfile.mkstemp(prefix="t_")
        os.close(fp)
        os.unlink(fname)
        os.mkfifo(fname)
        return fname

    def _errworker(self, errfile):
        if type(errfile) == int:
            fd = errfile
            errfile = None
        else:
            fd = os.open(errfile, os.O_RDONLY)
        try:
            while True:
                data = os.read(fd, 10240)
                if len(data) == 0:
                    break
                with self._errlock:
                    self._errout += data
        finally:
            self._errlock = None
            try:
                os.close(fd)
            except:
                pass
            try:
                if errfile:
                    os.unlink(errfile)
            except:
                pass

    def errread(self, errfile):
        self._errlock = Lock()
        t = Thread(target=self._errworker, kwargs={'errfile': errfile})
        t.daemon = True
        t.start()

    def err(self):
        with self._errlock:
            return self._errout

    def errclear(self):
        with self._errlock:
            self._errout = ""

def get_rendition(item, use, name=None, fp=None):
    if item.kind == 'I' and use == 'still':
        use = 'original'
    if not hasattr(item, 'saved_renditions'):
        item.saved_renditions = {}
    if use in item.saved_renditions:
        rendition = item.saved_renditions[use]
    elif use == 'original':
        rendition = item.original()
        item.saved_renditions[use] = rendition
    else:
        rendition = item.renditions.all()
        if use:
            rendition = rendition.filter(use=use)
        if name:
            rendition = rendition.filter(name=name)
        rendition = rendition.order_by('-created').first()
        if rendition:
            item.saved_renditions[use] = rendition
    if rendition and not hasattr(rendition, 'filename'):
        if fp:
            if type(fp) in (str, str):
                rendition.filename = fp
                rendition.fp = open(fp, "r")
            elif isinstance(fp, UploadedFile):
                sfx = fp.name
                ok_chars = string.ascii_letters + string.digits + "_-."
                "".join(list(a in ok_chars and a or "_" for a in sfx))
                rendition.fp = tempfile.NamedTemporaryFile(suffix=sfx, prefix=(str(item.pk) + "_"))
                rendition.filename = rendition.fp.name
                for buf in fp.chunks():
                    rendition.fp.write(buf)
            else:
                rendition.fp = fp
                rendition.filename = rendition.fp.name
        else:
            rendition.fp = tempfile.NamedTemporaryFile(suffix=('.' + rendition.ext()), prefix=(str(item.pk) + "_"))
            try:
                rendition.get_file(rendition.fp)
                rendition.filename = rendition.fp.name
            except Exception:
                rendition.fp.close()
                rendition.fp = None
                rendition.filename = rendition.get_local_url()
        try:
            if rendition.fp:
                rendition.fp.flush()
        except IOError:
            pass
        if rendition.fp:
            rendition.fp.seek(0)
    return rendition

def new_rendition(item, renditiondef, fp, kind, width=None, height=None, bytes=None, meta={}, direct=False):
    doclose = False
    if direct:
        fname = fp
        fp = None
    elif type(fp) in (str, str):
        fp = open(fp, 'r')
        doclose = True
    elif fp:
        fp.flush()
        fp.seek(0)

    if not bytes:
        if fp:
            bytes = os.fstat(fp.fileno()).st_size
        else:
            bytes = 0

    model = apps.get_model('medialib', 'MediaItemRendition')
    rendition = model(mediaitem=item, name=renditiondef.name, use=renditiondef.use, rendition_definition=renditiondef, kind=kind, width=width, height=height, bytes=bytes)
    if fp:
        rendition.upload(fp)
    elif direct:
        rendition.url = fname
    rendition.save()

    if fp:
        rendition.fp = fp
        rendition.filename = fp.name
    if not hasattr(item, 'saved_renditions'):
        item.saved_renditions = {}
    if renditiondef.use in item.saved_renditions:
        item.saved_renditions[renditiondef.use + '_' + str(renditiondef.pk)] = item.saved_renditions[renditiondef.use]
    item.saved_renditions[renditiondef.use] = rendition

    for m in meta:
        rendition.set_meta(m, meta[m])

    return rendition

def close_files(item):
    for rendition in getattr(item, 'saved_renditions', {}):
        if hasattr(rendition, 'fp'):
            rendition.fp.close()
    item.saved_renditions = {}

def calc_size(params, origwidth, origheight, even=True, rotate=0):
    try:
        if rotate:
            params['rotate'] = rotate
            if rotate == 90 or rotate == 270:
                x = origheight;
                origheight = origwidth;
                origwidth = x;
        if params.get('width', 0)>0 and params.get('height', 0)>0:
            if params['width'] > origwidth:
                params.pop("width")
                params.pop("height")
                return params
            return params
        if params.get('width', 0)>0:
            if params['width'] > origwidth:
                params.pop("width")
                params.pop("height")
                return params
            params['height'] = origheight * params['width'] / origwidth
            return params
        if params.get('height', 0)>0:
            params['width'] = origwidth * params['height'] / origheight
            return params

        if params.get('maxwidth', 0) == 0 and params.get('maxheight', 0) == 0:
            return params
        if params.get('maxwidth', 0) == 0:
            params['maxwidth'] = 100000
        if params.get('maxheight', 0) == 0:
            params['maxheight'] = 100000
        if params.get('minwidth', 0) == 0:
            params['minwidth'] = 0
        if params.get('minheight', 0) == 0:
            params['minheight'] = 0

        if params.get('maxaspect', 0)>0 and (origwidth * params['maxheight']) / (origheight * params['maxwidth']) > params['maxaspect']:
            # too wide
            params['width'] = params['maxaspect'] * (origheight * params['maxwidth']) / params['maxheight']
            if params['width'] < params['minwidth']:
                params['width'] = params['minwidth']
            params['height'] = params['maxheight']
            left = (origwidth - params['width']) / params['maxaspect']
            params['crop'] = (left, 0, left+params['width']-1, origheight-1)
            return params
        if params.get('maxaspect', 0)>0 and (origheight * params['maxwidth']) / (origwidth * params['maxheight']) > params['maxaspect']:
            # too tall
            params['height'] = params['maxaspect'] * (origwidth * lib.thumb_height) / lib.thumb_width
            if params['height'] < params['minheight']:
                params['height'] = params['minheight']
            params['width'] = params['maxwidth']
            top = (origheight - params['height'] ) / params['maxaspect']
            params['crop'] = (0, top, origwidth-1, top+params['height']-1)
            return params

        if origwidth > origheight:
            # wider
            if origwidth > params['maxwidth']:
                params['width'] = params['maxwidth']
                params['height'] = origheight * params['maxwidth'] / origwidth
            else:
                params['width'] = origwidth
                params['height'] = origheight
            if params['width'] < params['minwidth']:
                params['width'] = params['minwidth']
            if params['height'] < params['minheight']:
                params['height'] = params['minheight']
            return params
        else:
            # taller
            if origheight > params['maxheight']:
                params['width'] = origwidth * params['maxheight'] / origheight
                params['height'] = params['maxheight']
            else:
                params['width'] = origwidth
                params['height'] = origheight
            if params['width'] < params['minwidth']:
                params['width'] = params['minwidth']
            if params['height'] < params['minheight']:
                params['height'] = params['minheight']
            return params
    finally:
        if 'width' in params and not params['width']:
            params.pop('width')
        if 'height' in params and not params['height']:
            params.pop('height')
        if even and 'width' in params and params['width'] % 2 == 1:
            params['width'] += 1
        if even and 'height' in params and params['height'] % 2 == 1:
            params['height'] += 1
        if 'aspect' in params:
            if params['height'] * params['aspect'] > params['width']:
                params['height'] = params['width'] / params['aspect']
            elif params['height'] * params['aspect'] < params['width']:
                params['width'] = params['height'] * params['aspect']
        if 'width' in params and 'height' in params and (not 'crop' in params) and origheight and origwidth and params['width'] * origheight != params['height'] * origwidth:
            if params['width'] * origheight > params['height'] * origwidth:
                # too tall
                want = int(params['height'] * origwidth / params['width'])
                chop1 = int((origheight - want)/2)
                # NOTE: always calculate bottom from original to prevent double rounding errors
                params['crop'] = (0, chop1, origwidth-1, origheight-1-chop1)
            else:
                # too wide
                want = int(params['width'] * origheight / params['height'])
                chop1 = int((origwidth - want)/2)
                # NOTE: always calculate left from original to prevent double rounding errors
                params['crop'] = (chop1, 0, origwidth-1-chop1, origheight-1)
        if 'height' in params:
            params['height'] = int(params['height'])
        if 'width' in params:
            params['width'] = int(params['width'])
        if 'crop_x1' in params or 'crop_x2' in params or 'crop_y1' in params or 'crop_y2' in params:
            params['crop'] = (
                params.get('crop_x1', 0),
                params.get('crop_y1', 0),
                origwidth - 1 - params.get('crop_x2', 0),
                origheight - 1 - params.get('crop_y2', 0),
            )
        return params

def save_meta(rendition, meta):
    model = apps.get_model('medialib', 'MediaMeta')
    for k in meta:
        obj, _ = model.objects.get_or_create(rendition=rendition, key=k)
        obj.value = str(meta[k])
        obj.save()


