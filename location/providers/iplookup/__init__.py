from rest import settings
from rest import helpers as rh
import socket
import importlib

IP_LOOKUP_PROVIDERS = settings.get("IP_LOOKUP_PROVIDERS", [
    "ipinfo",
    "ipapi",
    "abstractapi",
])


def getLocation(ip):
    for key in IP_LOOKUP_PROVIDERS:
        provider = importlib.import_module(f"location.providers.iplookup.{key}")
        try:
            rsp = provider.getLocation(ip)
            float(rsp.latitude)
            return rsp
        except Exception:
            rh.log_exception(f"{key}.getLocation")
    return None


def isIP(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        pass
    return False


def dnsToIP(name):
    return socket.gethostbyname(name)
