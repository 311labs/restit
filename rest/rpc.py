from . import views

import version
import time
from datetime import datetime
import platform
import subprocess
from . import joke
from . import helpers

import django
from django.conf import settings


from .decorators import url

try:
    import psutil
except Exception:
    print("no psutil")


URL_PREFIX = ""

SOFTWARE_VERSIONS = getattr(settings, 'SOFTWARE_VERSIONS', None)
# SOFTWARE_VERSIONS_ACTUAL = {}


@url(r'^version$')
def on_get_version(request):
    return views.restStatus(request, True, {"data": version.VERSION})


@url(r'^joke$')
def on_get_joke(request):
    return views.restGet(request, {"joke": joke.getRandomJoke()})


def getTcpEstablishedCount():
    return len(getTcpEstablished())


def getTcpEstablished():
    cons = psutil.net_connections(kind="tcp")
    established = []
    for c in cons:
        if c.status == "ESTABLISHED":
            established.append(c)
    return established


@url(r'^system/info$')
def on_get_system_info(request):
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()

    out = {
        "time": time.time(),
        "datetime": str(datetime.now()),
        "version": version.VERSION,
        "os": {
            "system": platform.system(),
            "version": platform.version(),
            "hostname": platform.node(),
            "release": platform.release(),
            "processor": platform.processor(),
            "machine": platform.machine()
        },
        "cpu": {
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq(),
        },
        "boot_time": psutil.boot_time(),
        "cpu_load": psutil.cpu_percent(),
        "cpus_load": psutil.cpu_percent(percpu=True),
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        "network": {
            "tcp_cons": getTcpEstablishedCount(),
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "errin": net.errin,
            "errout": net.errout,
            "dropin": net.dropin,
            "dropout": net.dropout
        },
        "users": psutil.users()
    }
    if request.DATA.get("versions") and SOFTWARE_VERSIONS:
        out["versions"] = getVersions()
    if request.DATA.get("blocked"):
        out["blocked"] = getBlockedHosts()
    return views.restGet(request, out)


def safe_cmd(cmd, *args):
    try:
        cmd_args = [cmd]
        if len(args):
            cmd_args.extend(list(args))
        return helpers.toString(subprocess.check_output(cmd_args, shell=True).strip())
    except Exception as err:
        return str(err)
        # print( str(err))
    return None


def getVersions():
    out = {}
    for key in SOFTWARE_VERSIONS:
        if key == "django":
            out[key] = django.__version__
        else:
            out[key] = safe_cmd(SOFTWARE_VERSIONS[key])
    return out


def getBlockedHosts():
    blocked = []
    with open("/etc/hosts.deny", 'r') as f:
        for line in f.readlines():
            if line.startswith("#"):
                continue
            blocked.append(line.strip())
    return blocked




