from objict import objict
import requests


# THIS APPEARS TO BE DEAD?

def getLocation(ip):
    """
    https://extreme-ip-lookup.com/json/68.101.118.74
    {
     "businessName" : "",
     "businessWebsite" : "",
     "city" : "Dana Point",
     "continent" : "North America",
     "country" : "United States",
     "countryCode" : "US",
     "ipName" : "ip68-101-118-74.oc.oc.cox.net",
     "ipType" : "Residential",
     "isp" : "Cox Communications Inc.",
     "lat" : "33.46697",
     "lon" : "-117.69811",
     "org" : "Cox Communications Inc.",
     "query" : "68.101.118.74",
     "region" : "California",
     "status" : "success"
    }
    """
    # params = {"token":IPINFO_TOKEN}
    url = f"https://extreme-ip-lookup.com/json/{ip}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    data = objict.fromdict(res.json())

    loc = objict(provider="extreme api")
    loc.isp = data.isp
    loc.ip = data.ip
    loc.hostname = data.ipName
    loc.ip_type = data.ipType
    loc.latitude = data.lat
    loc.longitude = data.lon
    loc.continent = data.continent
    loc.region = data.region
    loc.country = data.country
    loc.countryCode = data.countryCode
    loc.state = data.region
    loc.city = data.city
    loc.business = data.businessName
    loc.website = data.businessWebsite
    return loc
