
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
