from medialib.models import *
from .render_utils import *
from .exceptions import *
from medialib import stores
from . import schedule
import os
from rest.mail import render_to_mail

from django.conf import settings

from datetime import datetime, timedelta
# import boto
import traceback
import socket
import json
import random

from rest.log import getLogger
logger = getLogger("medialib", filename="medialib.log")


def _log_verbose(msg, always=False):
    logger.info(msg)

def _log_null(msg, always=False):
    # if always:
    # 	print msg
    logger.info(msg)

def do_mail(item, mailtype, message=None):
    if getattr(settings, 'MEDIALIB_NOTIFY_OWNER', False):
        render_to_mail("medialib/mail_" + mailtype, {
            'item': item,
            'message': message,
            'settings': settings,
            'from': settings.MEDIALIB_MAIL_FROM,
            'to': [item.owner.email],
        })

def notify_mail(item, mailtype, message=None):
    render_to_mail("medialib/notify_" + mailtype, {
        'item': item,
        'message': message,
        'settings': settings,
        'from': settings.MEDIALIB_MAIL_FROM,
    })

def start_instance(log=None):
    """
    Start new rendering instance
    """
    if not (hasattr(settings, 'RENDER_AMI') and settings.RENDER_AMI and hasattr(settings, 'RENDER_IMAGE_TYPE') and hasattr(settings, 'RENDER_USER_DATA')):
        if log:
            log("NOT Starting instance")
        return
    # ec2 = boto.connect_ec2(settings.AWS_EC2_KEY, settings.AWS_EC2_SECRET)
    resv = ec2.run_instances(settings.RENDER_AMI, security_groups=settings.RENDER_SECURITY_GROUPS, instance_type=settings.RENDER_IMAGE_TYPE, user_data=settings.RENDER_USER_DATA, instance_initiated_shutdown_behavior='terminate')
    inst = resv.instances[0]
    try:
        inst.add_tag('Name', 'render-starting')
    except:
        pass
    RenderInstance(state="S", instance_id=inst.id).save()
    if log:
        log("Starting instance %s" % inst.id)

def demand_instance(log=None):
    """
    Start new rendering instance if called for
    """
    pending = MediaItem.objects.filter(state=101).count()
    instances = RenderInstance.objects.filter(state__in=('I','S','R',), last_checkin__gt=datetime.now()-timedelta(minutes=10)).count()
    if pending > instances * settings.RENDER_INSTANCE_RATIO:
        start_instance(log)

def rtmpcli_connect(url):
    if not stores.type(url) == "rtmpstore":
        return None

    host = stores.netloc(url)
    if not host:
        return None

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, 1112))
    except OSError:
        return None
    return s

def rtmpcli_do(cmd, url):
    s = rtmpcli_connect(url)
    if not s: return None

    s.send(cmd + "\n")
    s.shutdown(socket.SHUT_WR)
    buf = ""
    while True:
        nbuf = s.recv(1024)
        if nbuf:
            buf += nbuf
        else:
            break
    s.close()
    try:
        ret = json.loads(buf[buf.find('{'):])
    except ValueError:
        return None
    return ret

def live_allow(item):
    if not item.kind == 'L':
        return None

    url = item.live_local_url()
    if not url:
        return None

    ret = rtmpcli_do("start stream=%s" % url.split("/")[-1], url)
    return ret and (ret.get('status', None) == 'SUCCESS')

def live_end(item):
    if not item.kind == 'L':
        return None

    url = item.live_local_url()
    if not url:
        return None

    ret = rtmpcli_do("end stream=%s" % url.split("/")[-1], url)
    return ret and (ret.get('status', None) == 'SUCCESS')

def render_definition(item, rendition, params_override={}, verbose=False, log=None):
    if verbose and not log:
        log = _log_verbose
    if not log:
        log = _log_null

    log("rendering %s for %s" % (rendition.name, rendition.preset.module_name))
    params = {}
    for (n, (p, s, d,),) in list(rendition.getParameters(item=item).items()):
        if s == "" or s is None:
            pass
        elif p.kind == 'I':
            params[n] = int(s)
        elif p.kind == 'F':
            params[n] = float(s)
        elif p.kind == 'B':
            params[n] = bool(s)
        else:
            params[n] = str(s) \
                .replace("$(item)", str(item.pk)) \
                .replace("$(rendition)", str(rendition.pk)) \
                .replace("$(random)", str(random.randint(10000000, 99999999)))
    # print params_override
    # print params
    for p in params_override:
        params[p] = params_override[p]

    logger.info("params", params)
    try:
        back = __import__('medialib.render.presets.{0}'.format(rendition.preset.module_name), globals(), locals(), ['render'])
    except ImportError:
        logger.exception("Missing rendition back end for '%s'" % rendition.preset.module_name)
        raise RenderError("Missing rendition back end for %s" % rendition.preset.module_name)
    try:
        back.render(item, rendition, params)
        logger.info("rendering returned with no errors")
    except Exception:
        logger.exception("render_definition")

def render(item, stage=None, files={}, verbose=False, log=None, definition=None, use=None, params_override={}):
    """
    | Parameter: stage: rendition stage number (1 = initial, >1 = subsequent)
    | Parameter: files: manually specify pre-downloaded file
    | Parameter: verbose: verbose output
    | Parameter: log: logging function
    | Parameter: definition: render definition with specified name (in any rendition set)
    | Parameter: use: render presets with specified use (in handling rendition set)
    | Parameter: params_override: dictionary of override parameter settings

    | Return: REST list of all MediaLibrary data

    | Render media item
    """
    if verbose and not log:
        log = _log_verbose
    if not log:
        log = _log_null
    from ..models import MediaItemRendition, RenditionSet, MediaItem, RenditionDefinition
    ok = True
    try:
        try:
            # 10 minutes to upload original
            if not item.original().check_file():
                if (datetime.now() - item.created).total_seconds() > 600:
                    raise RenderError("Missing original rendition in storage")
                log("Skipped: original rendition not ready")
                return False
        except MediaItemRendition.DoesNotExist:
            if (datetime.now() - item.created).total_seconds() > 600:
                raise RenderError("Missing original rendition in DB")
            log("Skipped: original rendition not ready")
            return False

        if item.state == 100:
            isnew = True
            live_allow(item)
        else:
            isnew = False

        if item.state >= 100 and item.state <= 120:
            item.saveState(102)

        if definition:
            renditions = RenditionDefinition.objects.filter(active=True, name=definition)
            rset = None
        else:

            rset = item.library.rendition_sets.filter(kind=item.kind).first()
            if rset is None:
                rset = RenditionSet.objects.filter(kind=item.kind, default_set=True).first()
                if rset is None:
                    log("Invalid file kind: {0}".format(item.kind))
                    raise ValidateError("Invalid file type")
            renditions = rset.renditions.filter(active=True)
            if use:
                renditions = renditions.filter(use=use)
            # if stage:
            #     renditions = renditions.filter(preset__stage__gte=((stage-1)*100), preset__stage__lt=(stage*100))

        renditions = renditions.order_by('preset__stage', 'id')

        for f in files:
            get_rendition(item, f, fp=files[f])

        for rendition in renditions:
            render_definition(item, rendition, params_override=params_override, log=log)
        schedule.run()
        MediaItem.objects.update() # invalidate cache
        item = MediaItem.objects.get(pk=item.pk)
        if item.state >= 100 and item.state <= 120:
            if stage and rset and rset.renditions.filter(active=True).filter(preset__stage__gte=((stage)*100)).count() > 0:
                item.saveState(101)
            elif item.state != 200:
                item.render_error = None
                item.saveState(200)
                if not isnew and item.kind != 'L':
                    do_mail(item, 'ready')
                    if getattr(settings, 'MEDIALIB_NOTIFY_READY', False):
                        notify_mail(item, 'ready')
        if item.state >= 100 and item.state <= 120:
            if isnew:
                do_mail(item, 'pending')
                if getattr(settings, 'MEDIALIB_NOTIFY_PENDING', False):
                    notify_mail(item, 'pending')
            # demand_instance(log)
            # log("demanding instance but not allowed: {} {}".format(item.kind, item.state))
        if item.kind == 'L' and item.state >= 110:
            live_end(item)
            if item.state == 200:
                if isnew:
                    item.state = 100
                else:
                    item.state = 101
                item.kind = 'A'
                item.saveState(item.state)
                return render(item, 1, files=files, verbose=verbose, log=log, definition=definition, use=use, params_override=params_override)

    except ValidateError as err:
        item.render_error = err.message
        log(item.render_error, True)
        item.state = 111
        item.saveState(item.state)
        notify_mail(item, 'validate_error', item.render_error)
        return False
    except RenderError as err:
        item.render_error = err.message
        log(item.render_error, True)
        if not definition:
            item.state = 110
        item.saveState(item.state)
        do_mail(item, 'error', item.render_error)
        notify_mail(item, 'render_error', item.render_error)
        return False
    except:
        item.render_error = traceback.format_exc()
        log(item.render_error, True)
        if not definition:
            item.state = 110
        item.saveState(item.state)
        do_mail(item, 'error', item.render_error)
        notify_mail(item, 'error', item.render_error)
        return False
    finally:
        close_files(item)

    return True


