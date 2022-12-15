from objict import objict
from rest import settings
import requests

IPAPI_TOKEN = settings.get("GEOIP_IPAPI_TOKEN", "6551a9fe6f22a29bd4e4f176920a4646")


def getLocation(ip):
    """
    {
       "ip": "72.219.88.137",
       "type": "ipv4",
       "continent_code": "NA",
       "continent_name": "North America",
       "country_code": "US",
       "country_name": "United States",
       "region_code": "CA",
       "region_name": "California",
       "city": "Dana Point",
       "zip": "92629",
       "latitude": 33.485538482666016,
       "longitude": -117.69378662109375,
       "location":
       {
           "geoname_id": 5341483,
           "capital": "Washington D.C.",
           "languages":
           [
               {
                   "code": "en",
                   "name": "English",
                   "native": "English"
               }
           ],
           "country_flag": "https://assets.ipstack.com/flags/us.svg",
           "country_flag_emoji": "🇺🇸",
           "country_flag_emoji_unicode": "U+1F1FA U+1F1F8",
           "calling_code": "1",
           "is_eu": false
       }
    }
    """
    url = "http://api.ipapi.com/{}".format(ip)
    params = dict(access_key=IPAPI_TOKEN)
    resp = requests.get(url, params=params)
    data = objict.fromdict(resp.json())

    loc = objict(provider="ipapi.com")
    loc.isp = ""
    loc.ip = data.ip
    loc.hostname = ""
    loc.ip_type = data.type
    loc.latitude = data.latitude
    loc.longitude = data.longitude
    loc.continent = data.continent_name
    loc.region = data.region_name
    loc.country = data.country_name
    loc.countryCode = data.country_code
    loc.state = data.region_name
    loc.city = data.city
    loc.business = ""
    loc.website = ""
    loc.zipcode = data.zip
    return loc
