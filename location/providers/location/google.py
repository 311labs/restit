from rest import settings
import requests
from objict import objict

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACE_FROMTEXT_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def search(address, normalize=True):
    if settings.GOOGLE_MAPS_KEY is None:
        raise Exception("requires GOOGLE_MAPS_KEY")
    params = dict(address=address, key=settings.GOOGLE_MAPS_KEY)
    res = requests.get(GEOCODE_URL, params=params)
    if res.status_code != 200:
        return None
    if normalize:
        return normalizeResponse(res.json())
    return parseResponse(res.json())


def locationAt(lat, lng, normalize=True):
    if settings.GOOGLE_MAPS_KEY is None:
        raise Exception("requires GOOGLE_MAPS_KEY")
    params = dict(latlng=f"{lat},{lng}", key=settings.GOOGLE_MAPS_KEY)
    res = requests.get(GEOCODE_URL, params=params)
    if res.status_code != 200:
        return None
    if normalize:
        return normalizeResponse(res.json())
    return parseResponse(res.json())


def findPlaces(lat, lng, query="", radius_meters=50, normalize=True):
    if settings.GOOGLE_MAPS_KEY is None:
        raise Exception("requires GOOGLE_MAPS_KEY")
    params = dict(
        key=settings.GOOGLE_MAPS_KEY,
        input=query,
        inputtype="textquery",
        circular=f"circle:{radius_meters}@{lat,{lng}}")
    res = requests.get(GEOCODE_URL, params=params)
    if res.status_code != 200:
        return None
    if normalize:
        return normalizePlace(res.json())
    return parseResponse(res.json())


def parseResponse(response):
    locations = []
    results = response.get("results")
    for res in results:
        loc = objict.fromdict(res)
        locations.append(loc)
    return loc


GOOGLE_NORMALIZE_KEYS = {
    "locality": "city",
    "administrative_area_level_2": "county",
    "administrative_area_level_1": "state",
}


def normalizeResponse(response):
    locations = []
    results = response.get("results")
    for res in results:
        loc = objict(uuid=res.get("place_id", None), formatted=res.get("formatted_address", None))
        locations.append(loc)
        for comp in res.get("address_components"):
            key = comp.get("types", [None])[0]
            loc[GOOGLE_NORMALIZE_KEYS.get(key, key)] = comp.get("short_name")
        geometry = res.get("geometry", None)
        if geometry is not None:
            loc.update(geometry.get("location"))
    return locations


def normalizePlace(response):
    out = objict()
    out.name = response.name
    out.types = response.types
    out.place_id = response.place_id
    out.location = response.geometry.location
    out.photos = response.photos
    out.icon = response.icon
    out.address = response.formatted_address
    return out
