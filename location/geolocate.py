from .providers import iplookup
from .providers import timezones
from .providers import location

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


def locateByIP(ip):
    return iplookup.getLocation(ip)


def getTimeZone(lat, lng):
    """
    returns the timezone for a lat/lng
    """
    return timezones.getTimeZone(lat, lng)


def getAddress(lat, lng):
    """
    returns the address for a lat/lng
    """
    return location.locationAt(lat, lng)


def findLocationNear(lat, lng, query=None, radius_meters=100):
    return location.findPlaces(lat, lng, query, radius_meters)


def search(address):
    return location.search(address)


def isIP(ip):
    return iplookup.isIP(ip)


def dnsToIP(dns):
    return iplookup.dnsToIP(dns)
