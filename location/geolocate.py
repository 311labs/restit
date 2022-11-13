
import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse
import json
import time
import socket
import random

from django.conf import settings
import requests
try:
  from rest import helpers as rest_helpers
  from rest.uberdict import UberDict
except:
  rest_helpers = None

from datetime import datetime

from . import geocoder

"""
EXAMPLE GeoResult
{
    "address": "Co Rd 648, Birch Tree, MO 65438, USA",
    "administrative_area_level_1": "Missouri",
    "administrative_area_level_2": "Shannon County",
    "administrative_area_level_3": "Birch Tree Township",
    "bounds": {
        "northeast": {
            "lat": 36.9737638,
            "lng": -91.50315789999999
        },
        "southwest": {
            "lat": 36.9713575,
            "lng": -91.51723989999999
        }
    },
    "country": "United States",
    "latitude": 36.9734604,
    "locality": "Birch Tree",
    "location_type": "GEOMETRIC_CENTER",
    "longitude": -91.51131629999999,
    "postal_code": "65438",
    "route": "County Road 648",
    "short_administrative_area_level_1": "MO",
    "short_administrative_area_level_2": "Shannon County",
    "short_administrative_area_level_3": "Birch Tree Township",
    "short_country": "US",
    "short_locality": "Birch Tree",
    "short_postal_code": "65438",
    "short_route": "Co Rd 648",
    "types": [
        "route"
    ]
},
"""

GOOGLE_MAPS_KEY="XXXX"

STATES = {
    'Mississippi': 'MS', 'Oklahoma': 'OK', 'Delaware': 'DE', 'Minnesota': 'MN', 'Illinois': 'IL', 'Arkansas': 'AR',
    'New Mexico': 'NM', 'Indiana': 'IN', 'Maryland': 'MD', 'Louisiana': 'LA', 'Idaho': 'ID', 'Wyoming': 'WY',
    'Tennessee': 'TN', 'Arizona': 'AZ', 'Iowa': 'IA', 'Michigan': 'MI', 'Kansas': 'KS', 'Utah': 'UT',
    'Virginia': 'VA', 'Oregon': 'OR', 'Connecticut': 'CT', 'Montana': 'MT', 'California': 'CA',
    'Massachusetts': 'MA', 'West Virginia': 'WV', 'South Carolina': 'SC', 'New Hampshire': 'NH',
    'Wisconsin': 'WI', 'Vermont': 'VT', 'Georgia': 'GA', 'North Dakota': 'ND', 'Pennsylvania': 'PA',
    'Florida': 'FL', 'Alaska': 'AK', 'Kentucky': 'KY', 'Hawaii': 'HI', 'Nebraska': 'NE', 'Missouri': 'MO',
    'Ohio': 'OH', 'Alabama': 'AL', 'New York': 'NY', 'South Dakota': 'SD', 'Colorado': 'CO', 'New Jersey': 'NJ',
    'Washington': 'WA', 'North Carolina': 'NC', 'District of Columbia': 'DC', 'Texas': 'TX', 'Nevada': 'NV',
    'Maine': 'ME', 'Rhode Island': 'RI'}

class GeoResult(object):
  def __init__(self, **kwargs):
    self.city = kwargs.get("city", None)
    self.street_number = kwargs.get("street_number", None)
    self.route = kwargs.get("route", None)
    self.latitude = kwargs.get("latitude", None)
    self.longitude = kwargs.get("longitude", None)
    self.county = None
    self.country = None

    if len(kwargs):
      self.neighborhood = kwargs.get("neighborhood", None)
      self.cityCode = kwargs.get("cityCode", None)

      self.state = kwargs.get("state", None)
      self.stateCode = kwargs.get("stateCode", None)
      if self.stateCode is None and self.state in STATES:
        self.stateCode = STATES[self.state]
      self.county = kwargs.get("county", None)
      self.country = kwargs.get("country", None)
      self.countryCode = kwargs.get("countryCode", None)
      self.continent = kwargs.get("continent", None)

      self.isp = kwargs.get("isp", None)
      self.areaCode = kwargs.get("areaCode", None)
      self.postal = kwargs.get("postal", None)

  def asDict(self):
    out = self.__dict__.copy()
    if "res" in out:
      del out["res"]
    return out

class GeoTimeZone(object):
  def __init__(self, lat=None, lng=None):
    self.lat = lat
    self.lng = lng
    self.zone = None
    self.name = None
    self.offset = 0
    self.dst_offset = 0
    if self.lat and self.lng:
      self.update()

  def asDict(self):
    return self.__dict__

  def update(self):
    res = getTZ(self.lat, self.lng)
    if res:
      self.name = res.get("timeZoneName", None)
      self.zone = res.get("timeZoneId", None)
      if self.zone:
        when = datetime.now()
        dst_when = when.replace(month=1, day=1)
        self.dst_offset = rest_helpers.getTimeZoneOffset(self.zone, when=dst_when, dst=True)
        no_dst_when = when.replace(month=7, day=1)
        self.offset = rest_helpers.getTimeZoneOffset(self.zone, when=no_dst_when, dst=True)

def getTZ(lat, lng, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/timezone/json"
  params = {
    "location":"{},{}".format(lat, lng),
    "timestamp":0,
    "key": key
  }
  res = requests.get(url, params=params)
  if res.status_code == 200:
    return res.json()
  return None

def getTimeZone(lat, lng):
  res = getTZ(lat, lng)
  if not res:
    return None
  return res.get("zone")

def parseGoogleLocation(response):
  results = response.get("results")
  locations = []
  for res in results:
    location = GeoResult()
    for comp in res.get("address_components"):
      key = comp.get("types", [None])[0]
      if key != None:
        value = comp.get("long_name")
        short_value = comp.get("short_name")
        setattr(location, key, value)
        setattr(location, "short_{}".format(key), short_value)
    if "formatted_address" in res:
      location.address = res.get("formatted_address")
    geometry = res.get("geometry", None)
    if geometry:
      location.location_type = geometry.get("location_type", None)
      location.bounds = geometry.get("bounds", None)
      loc = geometry.get("location", None)
      location.latitude = loc.get("lat")
      location.longitude = loc.get("lng")
    location.types = res.get("types", None)
    if hasattr(location, "locality"):
      location.city = location.locality
    if hasattr(location, "administrative_area_level_2"):
      location.county = location.administrative_area_level_2

    locations.append(location)
  return locations

def getBestLocation(locations):
  if len(locations) == 0:
    return None

  for loc in locations:
    if "street_address" in loc.types:
      return loc

  for loc in locations:
    if "route" in loc.types:
      return loc

  return locations[0]

def search(location, return_one=True, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/geocode/json"
  params = {
    "address": location,
    "key":key
  }
  res = requests.get(url, params=params)
  if res.status_code == 200:
    data = res.json()
    locations = parseGoogleLocation(data)
    if return_one:
      out = getBestLocation(locations)
      if not out:
        return None
      out.search_location = location
      return out
    return locations
  return None

def reverse(lat, lng, return_one=True, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/geocode/json"
  params = {
    "latlng":"{},{}".format(lat, lng),
    "key":key
  }
  res = requests.get(url, params=params)
  if res.status_code == 200:
    data = res.json()
    locations = parseGoogleLocation(data)
    if return_one:
      out = getBestLocation(locations)
      out.search_location = "{},{}".format(lat, lng)
      return out
  return None

def parsePlace(res):
  out = UberDict()
  out.name = res.name
  out.types = res.types
  out.place_id = res.place_id
  out.location = res.geometry.location
  out.photos = res.photos
  out.icon = res.icon
  out.address = res.formatted_address
  return out

def parsePlaces(res, out=None):
  if out is None:
    out = []
  for plc in res.results:
    out.append(parsePlace(plc))
  return out

def findPlaceByZipcode(query, zipcode, radius_meters):
  loc = search(zipcode)
  return findNear(query, loc.latitude, loc.longitude, radius_meters)

def findTimezoneByZipcode(zipcode):
  loc = search(zipcode)
  return getTZ(loc.latitude, loc.longitude)

def findPlace(query, lat, lng, radius_meters, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
  params = {
    "key":key,
    "input": query,
    "inputtype": "textquery",
    "circular": "circle:{}@{},{}".format(radius_meters, lat, lng)
  }
  return placeRequest(url, params)

def placeRequest(url, params, key=GOOGLE_MAPS_KEY):
  res = requests.get(url, params=params)
  if res.status_code == 200:
    data = UberDict.fromdict(res.json())
    out = []
    out = parsePlaces(data, out)
    print(("got {} items".format(len(out))))
    while data.next_page_token:
      print(("getting more data: {}".format(len(out))))
      time.sleep(1.2)
      params = {"key":key, "pagetoken": data.next_page_token}
      res = requests.get(url, params=params)
      if not res.status_code == 200:
        print(("returned status: {}".format(res.status_code)))
        break
      data = UberDict.fromdict(res.json())
      out = parsePlaces(data, out)
      print(("got {} items".format(len(out))))
    return out
  return None

def findNear(query, lat, lng, radius_meters, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
  params = {
    "key":key,
    "location":"{},{}".format(lat, lng),
    "radius": radius_meters,
    "query": query,
  }
  return placeRequest(url, params)



def findPlaceDetails(place_id, key=GOOGLE_MAPS_KEY):
  url = "https://maps.googleapis.com/maps/api/place/details/json"
  params = {
    "latlng":"{},{}".format(lat, lng),
    "key":key,
    "placeid": place_id,
    "inputtype": "textquery",
    "circular": "circle:{}@{},{}".format(radius_meters, lat, lng)
  }

  res = requests.get(url, params=params)
  if res.status_code == 200:
    pass


def searchOld(location):
  res = geocoder.google(location, False)
  if res.status != "OK":
    return None

  loc = GeoResult(
    street_number=res.street_number,
    route=res.route,
    city=res.locality, 
    neighborhood=res.neighborhood,
    state=res.state, 
    country=res.country,
    postal=res.postal,
    latitude=res.lat,
    longitude=res.lng)

  res.short_name = True
  loc.countryCode = res.country
  loc.stateCode = res.state
  loc.cityCode = res.locality
  return loc


def reverseOld(lat, lng):
  res = geocoder.reverse((lat,lng), False)
  if res.status != "OK":
    return res

  loc = GeoResult(
    street_number=res.street_number,
    route=res.route,
    city=res.locality, 
    neighborhood=res.neighborhood,
    state=res.state, 
    country=res.country,
    postal=res.postal,
    latitude=res.lat,
    longitude=res.lng)

  res.short_name = True
  loc.countryCode = res.country
  loc.stateCode = res.state
  loc.cityCode = res.locality
  loc.res = res
  return loc


def is_ip(ip):
  try:
    socket.inet_aton(ip)
    return True
  except socket.error:
    pass
  return False


def ip(ip):
    providers = [ip_ipinfo, abstractapi_ip_lookup, ipapi_ip_lookup]
    random.shuffle(providers)
    for func in providers:
        try:
            resp = func(ip)
            # verify we got a real latitude back
            float(resp.latitude)
            return resp
        except Exception:
            pass
    return None


def dns_to_ip(name):
  return socket.gethostbyname(name)


IPINFO_TOKEN = "9ff8b6d9dd39b0"
def ip_ipinfo(ip):
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
        return None
    data = UberDict.fromdict(res.json())
    data.state = data.region
    data.isp = data.org

    loc = UberDict(provider="ipinfo")
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

# ip lookup apis

# https://extreme-ip-lookup.com/json/68.101.118.74
def ip_extreme_ip(ip):
  """
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
  url = "https://extreme-ip-lookup.com/json/{}".format(ip)
  res = requests.get(url)
  if res.status_code != 200:
    return None
  data = UberDict.fromdict(res.json())

  loc = UberDict(provider="extreme api")
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


# GEOPLUGIN API
_URL = "http://www.geoplugin.net/json.gp"
_URL_LAT = "http://www.geoplugin.net/extras/location.gp?lat={0}&long={1}&format=json"

def normalizeResponse(response):
    ret = {}
    data = json.loads(response)
    if "geoplugin_latitude" in data:
        ret["lat"] = data["geoplugin_latitude"]
        ret["lng"] = data["geoplugin_longitude"]
    if "geoplugin_city" in data:
        ret["city"] = data["geoplugin_city"]
    if "geoplugin_countryCode" in data:
        ret["country"] = data["geoplugin_countryCode"]
    if "geoplugin_region" in data:
        ret["region"] = data["geoplugin_region"]
    return ret

def _makeRequest(query_args, url):
    # This urlencodes your data (that's why we need to import urllib at the top)
    data = urllib.parse.urlencode(query_args)
    # Send HTTP POST request
    request = urllib.request.Request("{0}?{1}".format(url, data))
    try:
        return normalizeResponse(urllib.request.urlopen(request).read())
    except:
        pass
    return None

def byIP(ip):
    """
    simple geolocation by ip
      "geoplugin_request":"72.211.193.165",
      "geoplugin_status":200,
      "geoplugin_credit":"Some of the returned data includes GeoLite data created by MaxMind, available from <a href=\\'http:\/\/www.maxmind.com\\'>http:\/\/www.maxmind.com<\/a>.",
      "geoplugin_city":"San Clemente",
      "geoplugin_region":"CA",
      "geoplugin_areaCode":"949",
      "geoplugin_dmaCode":"803",
      "geoplugin_countryCode":"US",
      "geoplugin_countryName":"United States",
      "geoplugin_continentCode":"NA",
      "geoplugin_latitude":"33.422798",
      "geoplugin_longitude":"-117.620102",
      "geoplugin_regionCode":"CA",
      "geoplugin_regionName":"California",
      "geoplugin_currencyCode":"USD",
      "geoplugin_currencySymbol":"&#36;",
      "geoplugin_currencySymbol_UTF8":"$",
      "geoplugin_currencyConverter":1
    """
    # Prepare the data
    query_args = {
        'ip':ip,
    }

    # t = threading.Thread(target=_makeRequest, args=[query_args])
    # t.setDaemon(True)
    # t.start()
    return _makeRequest(query_args, _URL)


IPAPI_STACK_KEY = "6551a9fe6f22a29bd4e4f176920a4646"

def ipapi_ip_lookup(ip):
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
    params = dict(access_key=IPAPI_STACK_KEY)
    resp = requests.get(url, params=params)
    data = UberDict.fromdict(resp.json())

    loc = UberDict(provider="ipapi.com")
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


ABSTRACTAPI_KEY = "817a0affd6b6462189264bc828d0d9f9"
def abstractapi_ip_lookup(ip):
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
    params = dict(api_key=ABSTRACTAPI_KEY)
    resp = requests.get("https://ipgeolocation.abstractapi.com/v1/", params=params)
    data = UberDict.fromdict(resp.json())

    loc = UberDict(provider="abstracapi")
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




