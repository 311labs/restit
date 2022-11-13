import collections
import inspect
import re
import sys

def guess_wrapper(cells):
    # look through the funciton closure for cells that look
    # like wrapped functions. for multuple functions,
    # attempt to guess which is the more likely candidate

    # we add points for
    # * non-lambda
    # * 'request' in arg list

    functions = collections.defaultdict(list)
    for cell in cells:
        contents = cell.cell_contents
        if not inspect.isfunction(contents):
            continue

        score = 0
        if contents.__name__ != '<lambda>':
            score += 1
        if 'request' in inspect.getargspec(contents).args:
            score += 1

        functions[score].append(contents)

    for score in reversed(sorted(functions.keys())):
        return functions[score][0]
    return None


def unwrap_and_compare(kwargs_provided, callback, description):
    # if the callback is decorated, unwrap to find the
    # original view

    # if we have a decorated function, the "wrapped"
    # function should b in the closure of the decorator
    # so we look for functions in the closure, guessing
    # if neccessary.

    if callback is not None:
        while callback.__closure__:
            compare(kwargs_provided, callback, description)
            cells = callback.__closure__
            guess = guess_wrapper(cells)
            if guess:
                callback = guess
            else:
                # nothing in the closure was a function, so give up
                break
        compare(kwargs_provided, callback, description)
        return callback



def compare(kwargs_provided, callback, description):
    spec = inspect.getargspec(callback)

    args = spec.args
    defaults = spec.defaults
    if defaults:
        required_args = args[:-len(defaults)]
    else:
        required_args = args

    missing_kwargs = set(required_args) - kwargs_provided
    if missing_kwargs:
        print(("%s: view requires kwargs %s not in the url kwargs" % (
            description, list(missing_kwargs))))


    if spec.keywords:
        # signature contains **kwargs, so can't do second check
        return

    extra_kwargs = kwargs_provided - set(args)
    if extra_kwargs:
        print(("%s: url provides kwargs %s not in the view signature" % (
            description, list(extra_kwargs))))



def check_resolver(entry, prefix):
    effective_regex = re.compile(prefix + entry.regex.pattern)

    # skip the admin
    if effective_regex.pattern.startswith('^admin/'):
        return
    #print dir(entry)
    description = (getattr(entry, 'name', None) or effective_regex.pattern)

    kwargs_provided = set(['request'] + list(getattr(entry, 'default_args', {}).keys()))
    #print kwargs_provided
    kwargs_provided.update(list(effective_regex.groupindex.keys()))
    callback = unwrap_and_compare(kwargs_provided, entry.callback, description)

    url_request = {"url":description, "methods":{}, "args": list(effective_regex.groupindex.keys())}
    if hasattr(entry, 'default_args'):
        dargs = getattr(entry, 'default_args', {})
        if "__MODULE" in dargs:
            url_request["module"] = dargs["__MODULE"].__name__
            method_patterns = dargs["__MODULE"].urlpattern_methods
            if entry.regex.pattern + "__GET" in method_patterns:
                url_request["methods"]["get"] = {"callback": method_patterns[entry.regex.pattern+ "__GET"]}
            if entry.regex.pattern + "__POST" in method_patterns:
                url_request["methods"]["post"] = {"callback": method_patterns[entry.regex.pattern+ "__POST"]}
            if entry.regex.pattern + "__DELETE" in method_patterns:
                url_request["methods"]["delete"] = {"callback": method_patterns[entry.regex.pattern+ "__DELETE"]}
            if entry.regex.pattern + "__PUT" in method_patterns:
                url_request["methods"]["put"] = {"callback": method_patterns[entry.regex.pattern+ "__PUT"]}
    if "module" not in url_request and callback:
        url_request["module"] = callback.__module__
    url_request["callback"] = callback


    #print dir(callback)
    return url_request


def show_urls(urllist, apis, filter=None, prefix=''):
    for entry in urllist:
        api = check_resolver(entry, prefix)
        if api:
            api["url"] = api["url"].replace("^", "").replace("$", "")
            if (filter and api["url"].startswith(filter)) or filter is None:
                if api["callback"].__doc__:
                    api["doc"] = api["callback"].__doc__
                else:
                    api["doc"] = None
                apis.append(api)

        if hasattr(entry, 'url_patterns'):
            show_urls(entry.url_patterns, apis, filter, prefix + entry.regex.pattern)

def sanatizeUrl(url):
    return re.sub(r'\(\?P<(.*?)>.*?\)',r'{\1}',url)

def parseDoc(api, graphs):
    """
    did regex, this approached seems to work better
    """
    doc = {"params":{}, "graphs":"", "summary":"", "issues":"", "returns":""}

    key = None
    subkey = None

    for line in api["doc"].split("\n"):
        linestr = line.strip()
        if linestr.startswith('|'):
            linestr = linestr[1:].strip()
            line = line.strip()[1:]
        lower_line = linestr.lower()
        if lower_line.startswith("parameter:") or lower_line.startswith("param:"):
            name = line[line.find(':')+1:line.find('=')].strip()
            info = line[line.find('=')+1:]
            doc["params"][name] = info
            key = "params"
            subkey = name
        elif lower_line.startswith("return:"):
            doc["returns"] = line[line.find(':')+1:].strip()
            key = "summary"
            subkey = None
        elif lower_line.startswith("issues:"):
            doc["issues"] = line[line.find(':')+1:].strip()
            key = "issues"
            subkey = None
        elif lower_line.startswith("graphs:"):
            doc["graphs"] = line[line.find(':')+1:].strip()
            key = "graphs"
            subkey = None
        elif key and subkey:
            doc[key][subkey] = "{0}\n{1}".format(doc[key][subkey], line.strip())
        elif key:
            doc[key] = "{0}\n{1}".format(doc[key], line.strip())
    doc["summary"] = doc["summary"].strip()

    if False: # doc["graphs"]
        graph_names = []
        fields = doc["graphs"].split('=')
        # print fields
        key = None
        value = None
        while len(fields):
            val = fields.pop(0)
            vals = val.strip()
            if vals.endswith("_graph"):
                epos = max(val.rfind(' '), val.rfind('\n'))
                nkey = val[epos:].strip()
                if epos > 0:
                    if value:
                        value = "{0}={1}".format(value, val[:epos].strip())
                    else:
                        value = val[:epos].strip()

                if key and value:
                    if key not in graphs:
                        graphs[key] = value
                    graph_names.append(key)
                key = nkey
            elif key:
                value = "{0}={1}".format(value, val)
        if key and value:
            if key not in graphs:
                graphs[key] = value
            graph_names.append(key)

        if "_graph" in doc["graphs"]:
            words = doc["graphs"].split()
            for word in words:
                if word.strip().endswith("_graph"):
                    graph_names.append(word.strip())
        doc["graphs"] = graph_names
    elif "_graph" in doc["returns"]:
        if "_graph" in doc["returns"]:
            graph_names = []
            words = doc["returns"].split()
            for word in words:
                if word.strip().endswith("_graph"):
                    graph_names.append(word.strip())
            doc["graphs"] = graph_names

    return doc

import json
def dumpGraphs(module_name, graphs):
    if module_name not in sys.modules:
        print("MODULE NOT LOADED.. loading")
        return
    module = sys.modules[module_name]
    for name in module.__dict__:
        # if "getMyself" in name:
        #     print "+++++++++++++++++"
        #     func = getattr(module, name)
        #     print func.__doc__
        #     print dir(func)
        #     print func.__dict__

        if "_graph" in name:
            graph = getattr(module, name)
            # print graph.keys()
            dc = {}
            if "fields" in graph:
                fields = graph["fields"]
                graph_doc = {}
                for f in fields:
                    if type(f) is tuple:
                        o = f[0]
                        f = f[1]
                        if len(f):
                            if "." in o:
                                o = o[:o.rfind('.')]
                                f = "{0}.{1}".format(o, f)
                    if "." in f:
                        levels = f.split('.')
                        current = graph_doc
                        field = levels[-1]
                        for o in levels:
                            if o is field:
                                continue
                            if o not in current:
                                current[o] = {}
                            elif type(current[o]) is str:
                                current[o] = {}
                            current = current[o]
                        current[field] = ''
                    else:
                        graph_doc[f] = ''
                graphs[name] = json.dumps(graph_doc)


def getRestApis(patterns, sanatize_urls=True):
    apis = []
    graphs = {}
    modules = []
    show_urls(patterns, apis)
    if sanatize_urls:
        old_apis = apis
        apis = []
        for api in old_apis:
            if len(api["methods"]):
                for method in api["methods"]:
                    a = {"method":method}
                    m = api["methods"][method]
                    module_name = m["callback"].__module__
                    if module_name not in modules:
                        dumpGraphs(module_name, graphs)
                        modules.append(module_name)

                    a["url"] = api["url"]
                    # print a["url"]

                    # # print m["callback"].func_doc
                    # if not m["callback"].__doc__:
                    #     print dir(m["callback"].__code__)
                    #     print m["callback"].__code__.__doc__
                    if m["callback"].__doc__:
                        # print "\tyes we have docs"
                        a["doc"] = m["callback"].__doc__
                        a["doc"] = parseDoc(a, graphs)
                        if a["doc"] is None or len(a["doc"]) == 0:
                            a["doc"] = ""
                        apis.append({
                            "module":api["module"].replace(".rpc", ""),
                            "method":method,
                            "url":sanatizeUrl(a["url"]),
                            "doc":a["doc"]
                        })
                    else:
                        apis.append({
                            "module":api["module"].replace(".rpc", ""),
                            "method":method,
                            "url":sanatizeUrl(a["url"]),
                            "doc":""
                        })
                        # print "\tno docs"
            else:
                # print api
                if api["doc"] is None or len(api["doc"]) == 0:
                    continue
                api["doc"] = parseDoc(api, graphs)
                apis.append({
                    "module":api["module"].replace(".rpc", ""),
                    "method":"*",
                    "url":sanatizeUrl(api["url"]),
                    "doc":api["doc"]
                    })
    return apis, graphs

