from objict import objict
from rest import settings
import requests

GEOIP_RESTIT_HOST = settings.get("GEOIP_RESTIT_HOST", "api.payauth.io")


def getLocation(ip):
    """
    {
        "id": 14770,
        "created": 1653767808.0,
        "modified": 1671040424.0,
        "hostname": "ip70-187-221-89.oc.oc.cox.net",
        "ip": "70.187.221.89",
        "isp": "AS22773 Cox Communications Inc.",
        "provider": "ipinfo",
        "city": "Rancho Santa Margarita",
        "state": "California",
        "country": "US",
        "postal": None,
        "lat": 33.6409,
        "lng": -117.6031
    }
    """
    params = {"ip": ip}
    url = f"https://{GEOIP_RESTIT_HOST}/rpc/location/ip/lookup"
    res = requests.get(url, params=params)
    if res.status_code != 200:
        return None
    data = objict.fromdict(res.json())
    data.provider = GEOIP_RESTIT_HOST
    return data.data
