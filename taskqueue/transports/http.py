import requests
import time
REQ_TIMEOUT = 15.0
from rest.uberdict import UberDict

def POST(task, attempts=3, timeout=REQ_TIMEOUT, headers=None):
    while attempts:
        try:
            started = time.time()
            attempts -= 1
            data = task.data.data
            resp = httpPOST(task.data.url, data, isinstance(data, (dict, list)), timeout=timeout, headers=headers)
            task.log(resp.text)
            if resp.status_code == 200:
                return resp
        except requests.Timeout:
            task.log("timed out after {}s".format(time.time()-started), kind="error")
        except Exception as err:
            task.log_exception(err)
    return None

def GET(task, attempts=3, timeout=REQ_TIMEOUT):
    while attempts:
        try:
            started = time.time()
            attempts -= 1
            resp = httpGET(task.data.url, params=task.data.data, timeout=timeout)
            task.log(resp.text)
            if resp.status_code == 200:
                return resp
        except requests.Timeout:
            task.log("timed out after {}s".format(time.time()-started), action="error")
        except Exception as err:
            task.log_exception(err)
    return None


def httpGET(url, params=None, session=None, timeout=REQ_TIMEOUT):
    headers = {'Accept': 'application/json'}
    if session:
        res = session.get(url, headers=headers, params=params, timeout=timeout)
    else:
        res = requests.get(url, headers=headers, params=params, timeout=timeout)
    return res

def httpPOST(url, data, post_json=False, session=None, timeout=REQ_TIMEOUT, headers=None):
    if not headers or type(headers) is not dict:
        headers = {'Accept': 'application/json'}
    if 'Accept' not in headers:
        headers['Accept'] = 'application/json'
    if post_json:
        data = UberDict(data).toJSON()
        headers['Content-type'] = 'application/json'
    if post_json:
        if session:
            res = session.post(url, json=data, headers=headers, timeout=timeout, verify=False)
        else:
            res = requests.post(url, json=data, headers=headers, timeout=timeout, verify=False)
    else:
        if session:
            res = session.post(url, data=data, headers=headers, timeout=timeout, verify=False)
        else:
            res = requests.post(url, data=data, headers=headers, timeout=timeout, verify=False)
    return res
