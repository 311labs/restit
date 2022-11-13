import re

from django.db.models import Q
from .datem import parseDateTime, parseDate
from rest import helpers
from datetime import datetime, timedelta

SEARCH_COMPARES = [
    "==",
    "<=",
    ">=",
    "!=",
    ">",
    "<",
    ":",
    "=",
]

COMPARATOR_TO_FILTER = {
    ":": "icontains",
    "=":"icontains",
    "==":"iexact",
    "<":"lt",
    "<=":"lte",
    ">":"gt",
    ">=":"gte",
    "!=":"not"
}

TRUE_VALUES = ['1', 'Y', 'y', 'yes', 'True', 'true']


def filter(qset, query_string, search_fields, value_fields=[]):
    fq = get_query(query_string, search_fields, value_fields)
    if fq:
        qset = qset.filter(fq)
    sq = get_query(query_string, search_fields, value_fields, excludes=True)
    if sq:
        qset = qset.exclude(sq) 
    return qset

def parseComparison(term):
    comp = None
    comparators = [e for e in SEARCH_COMPARES if e in term]
    if not comparators:
        return None, None, None
    comp = comparators[0]
    dfilter = COMPARATOR_TO_FILTER.get(comp)
    try:
        field, sterm = term.split(comp)
        return field, sterm, dfilter
    except:
        pass
    return None, None, None

def normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    ''' Splits the query string in invidual keywords, getting rid of unecessary spaces
        and grouping quoted words together.
        Example:

        >>> normalize_query('  some random  words "with   quotes  " and   spaces')
        ['some', 'random', 'words', 'with quotes', 'and', 'spaces']

    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]

def get_properties_search(fname, fields, tfilter, tvalue):
    key = fields[1]
    if "." in key:
        # examples "properties|. would be properties(key=tvalue, value__in=[1, 'y', 'Y', 'True', 'true'])"
        # examples "properties|permissions. would be properties(category="permissions", key=tvalue, value__in=[1, 'y', 'Y', 'True', 'true'])"
        category, key = key.split('.')
        if not category:
            # this means there is no category and the value is the key
            category = None
        if not key:
            # this means the value is the key
            key = tvalue
            qq = {"properties__key":key, "properties__category":category, "properties__value__in": TRUE_VALUES}
        else:
            qq = {"properties__key":key, "properties__category":category, "properties__value__{}".format(tfilter): tvalue}
    else:
        qq = {"properties__key":key, "properties__category":None, "properties__value__{}".format(tfilter): tvalue}
    q = Q(**qq)
    return q

def get_datetime_query(fname, fields, tfilter, tvalue):
    try:
        if isinstance(tvalue, str):
            if tvalue[-1] in ["h", "d", "m", "y"]:
                span = tvalue[-1]
                value = int(tvalue[:-1])
                if span == "h":
                    tvalue = datetime.now() + timedelta(hours=value)
                elif span == "d":
                    tvalue = datetime.now() + timedelta(days=value)
                elif span == "m":
                    tvalue = datetime.now() + timedelta(months=value)
                elif span == "y":
                    tvalue = datetime.now() + timedelta(years=value)
            else:
                tvalue = parseDateTime(tvalue)
        if tvalue is None:
            return None
        fname = fields[0]
        if tfilter == "icontains":
            tfilter = "gte"
        return Q(**{"{0}__{1}".format(fname, tfilter): tvalue})
    except Exception:
        pass
    return None

def get_query(query_string, search_fields, value_fields=[], default_filter="icontains", excludes=False):
    ''' Returns a query, that is a combination of Q objects. That combination
        aims to search keywords within a model by testing the given search fields.

    '''
    helpers.log_print(search_fields)
    query = None # Query to search for every search term
    terms = normalize_query(query_string)
    # copy search fields
    if search_fields is None:
        search_fields = []
    search_fields = search_fields[:]
    value_fields_keys = []
    value_fields_map = {}
    remove_terms = []
    for term in terms:
        or_query = None # Query to search for a given term in each field
        tfield, tvalue, tfilter = parseComparison(term)
        helpers.log_print("{}, {}, {}".format(tfield, tvalue, tfilter))
        if excludes:
            # only get excludes which is the "not"
            if tfilter != "not":
                continue
            tfilter = "icontains"
        if tfilter == "not":
            continue
        if tfilter:
            # we have a comparison term being used
            if value_fields and not value_fields_keys:
                # lets build a mapping for keys with simple terms like last_name == account__last_name
                for key in value_fields:
                    if isinstance(key, tuple):
                        value_fields_keys.append(key[0])
                        value_fields_map[key[0]] = key[1]
                    else:
                        value_fields_keys.append(key)
                        value_fields_map[key] = key
            if not tfield:
                # we need to search all fields
                for field_name in value_fields:
                    fname = field_name
                    if isinstance(field_name, tuple):
                        fname = field_name[0]
                    q = Q(**{"{0}__{1}".format(fname, tfilter): tvalue})
                    if or_query is None:
                        or_query = q
                    else:
                        or_query = or_query | q
            elif tfield in search_fields:
                q = Q(**{"{0}__{1}".format(tfield, tfilter): tvalue})
            elif tfield in value_fields_keys:
                # now we need to find the
                fname = value_fields_map[tfield]
                if "|" in fname:
                    # this is a special type
                    fields = fname.split('|')
                    if fields[0] == "properties":
                        q = get_properties_search(fname, fields, tfilter, tvalue)
                    else:
                        continue
                elif "#" in fname:
                    fields = fname.split('#')
                    if fields[1] == "datetime":
                        q = get_datetime_query(fname, fields, tfilter, tvalue)
                        if not q:
                            continue
                    else:
                        continue
                else:
                    q = Q(**{"{0}__{1}".format(fname, tfilter): tvalue})
            else:
                # field is not supported in search
                remove_terms.append(term)
                helpers.log_print("field: '{}'' not supported in search".format(tfield), value_fields_keys)
                continue
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        elif search_fields:
            # simple search so lets search all fields
            for field_name in search_fields:
                q = Q(**{"{0}__{1}".format(field_name, default_filter): term})
                if or_query is None:
                    or_query = q
                else:
                    or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    terms = [x for x in terms if x not in remove_terms]
    return query


