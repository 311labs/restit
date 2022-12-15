from objict import objict
from rest import settings
import requests

ABSTRACTAPI_TOKEN = settings.get("GEOIP_ABSTRACTAPI_TOKEN", "817a0affd6b6462189264bc828d0d9f9")


def getLocation(ip):
    """
    {
        "ip_address": "72.219.88.137",
        "city": "Dana Point",
        "city_geoname_id": 5341483,
        "region": "California",
        "region_iso_code": "CA",
        "region_geoname_id": 5332921,
        "postal_code": "92629",
        "country": "United States",
        "country_code": "US",
        "country_geoname_id": 6252001,
        "country_is_eu": false,
        "continent": "North America",
        "continent_code": "NA",
        "continent_geoname_id": 6255149,
        "longitude": -117.7013,
        "latitude": 33.4769,
        "security":
        {
            "is_vpn": false
        },
        "timezone":
        {
            "name": "America/Los_Angeles",
            "abbreviation": "PST",
            "gmt_offset": -8,
            "current_time": "21:55:15",
            "is_dst": false
        },
        "flag":
        {
            "emoji": "🇺🇸",
            "unicode": "U+1F1FA U+1F1F8",
            "png": "https://static.abstractapi.com/country-flags/US_flag.png",
            "svg": "https://static.abstractapi.com/country-flags/US_flag.svg"
        },
        "currency":
        {
            "currency_name": "USD",
            "currency_code": "USD"
        },
        "connection":
        {
            "autonomous_system_number": 22773,
            "autonomous_system_organization": "ASN-CXA-ALL-CCI-22773-RDC",
            "connection_type": "Corporate",
            "isp_name": "Cox Communications Inc.",
            "organization_name": "Cox Communications Inc."
        }
    }
    """
    params = dict(api_key=ABSTRACTAPI_TOKEN)
    resp = requests.get("https://ipgeolocation.abstractapi.com/v1/", params=params)
    data = objict.fromdict(resp.json())

    loc = objict(provider="abstracapi")
    loc.isp = data.isp_name
    loc.ip = data.ip_address
    loc.hostname = ""
    loc.ip_type = ""
    loc.latitude = data.latitude
    loc.longitude = data.longitude
    loc.continent = data.continent
    loc.region = data.region
    loc.country = data.country
    loc.countryCode = data.country_code
    loc.state = data.region_iso_code
    loc.city = data.city
    loc.business = ""
    loc.website = ""
    loc.zipcode = data.postal_code
    return loc

