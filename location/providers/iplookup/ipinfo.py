from objict import objict
from rest import settings
import requests

IPINFO_TOKEN = settings.get("GEOIP_IPINFO_TOKEN", "9ff8b6d9dd39b0")


def getLocation(ip):
    """
    {
    "ip": "12.173.248.130",
    "city": "Gatlinburg",
    "region": "Tennessee",
    "country": "US",
    "loc": "35.7145,-83.5119",
    "org": "AS7018 AT&T Services, Inc.",
    "postal": "37738",
    "timezone": "America/New_York",
    "readme": "https://ipinfo.io/missingauth"
    }
    """
    params = {"token": IPINFO_TOKEN}
    url = "https://ipinfo.io/{}/json".format(ip)
    res = requests.get(url, params=params)
    if res.status_code != 200:
        print(res.text)
        return None
    data = objict.fromdict(res.json())
    data.state = data.region
    data.isp = data.org

    loc = objict(provider="ipinfo")
    loc.isp = data.isp
    loc.ip = data.ip
    loc.hostname = data.hostname
    loc.ip_type = ""
    data.lat, data.lon = data.loc.split(',')
    loc.latitude = data.lat
    loc.longitude = data.lon
    loc.continent = ""
    loc.region = data.region
    loc.country = data.country
    loc.countryCode = data.country
    loc.state = data.region
    loc.city = data.city
    loc.business = data.org
    loc.website = ""
    loc.zipcode = data.postal
    return loc
