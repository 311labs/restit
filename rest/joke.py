import requests

def getRandomJoke():
    r = requests.get('https://icanhazdadjoke.com/', headers={"Accept":"application/json"})
    try:
        data = r.json()
        return data.get("joke", "failed")
    except:
        pass
    return "Tired, try later."
