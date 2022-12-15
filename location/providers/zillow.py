ZWSID = "X1-ZWz194856f3evf_22g4o"

import requests
try:
    import xmltodict
except:
    pass

def buildPost(**kwargs):
    data = {}
    for key, value in list(kwargs.items()):
        if value:
            data[key] = value
    return data

def getPropertyValue(address=None, street1=None, street2=None, city=None, state=None, zipcode=None,**kwargs):
    url = "https://www.zillow.com/webservice/GetSearchResults.htm"
    params = {"zws-id":ZWSID}
    if address:
        if hasattr(address, "street1"):
            params["address"] = address.street1
            params["citystatezip"] = "{} {} {}".format(address.city, address.state, address.zipcode)
        elif hasattr(address, "line1"):
            params["address"] = address.line1
            params["citystatezip"] = "{} {} {}".format(address.city, address.state, address.postalcode)
        else:
            return None
    elif street1:
        params["address"] = street1
        zipcode = str(zipcode)
        if len(zipcode) > 5:
            zipcode = zipcode[:5]
        params["citystatezip"] = "{} {} {}".format(city, state, zipcode)
    else:
        return None

    print(params)
    resp = requests.get(url, params=params, timeout=15.0)
    print((resp.text))
    data = xmltodict.parse(resp.text)
    result = None
    results = data["SearchResults:searchresults"]["response"]["results"]
    if isinstance(results, list) and len(results):
        result = results[0]
    elif isinstance(results, dict):
        result = results["result"]
    if result:
        out = {}
        if "links" in result:
            out["map_url"] = result["links"].get("mapthishome", None)
        if "zestimate" in result and "amount" in result["zestimate"]:
            out["value"] = float(result["zestimate"]["amount"].get("#text", 0))
        out["zpid"] = result.get("zpid", None)
        out["address"] = result.get("address", None)
        result = out
    return result

