from rest import settings
import requests

TZ_URL = "https://maps.googleapis.com/maps/api/timezone/json"


def getTimeZone(lat, lng):
    rsp = lookup(lat, lng)
    if rsp is not None:
        return rsp.get("timeZoneId", None)
    return None
    

def lookup(lat, lng):
    if settings.GOOGLE_MAPS_KEY is None:
        raise Exception("requires GOOGLE_MAPS_KEY")
    params = dict(location=f"{lat},{lng}", timestamp=0, key=settings.GOOGLE_MAPS_KEY)
    rsp = requests.get(TZ_URL, params)
    print(rsp.text)
    if rsp.status_code == 200:
        rsp = rsp.json()
        return rsp.get("zone", None)
    return None
