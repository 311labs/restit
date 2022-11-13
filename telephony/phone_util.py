from django.conf import settings
from rest import UberDict
import phonenumbers

try:
    import twilio
    import twilio.rest
except ImportError:
    pass

client = twilio.rest.Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)


def lookup(number, country="US", name_lookup=True):
    extra_info = ['carrier']
    if name_lookup:
        extra_info.append("caller-name")
    number = normalize(number, country)
    output = UberDict(success=False)
    try:
        resp = client.lookups.v1.phone_numbers(number).fetch(type=extra_info)
    except Exception as err:
        output.reason = str(err)
        return output
    output.success = True
    output.number = number
    output.carrier = UberDict.fromdict(resp.carrier)
    if resp.caller_name:
        output.owner_name = resp.caller_name.get("caller_name", None)
        output.owner_kind = resp.caller_name.get("caller_type", None)
    return output


def sendSMS(to_num, from_num, msg, country="US"):
    to_num = normalize(to_num, country)
    from_num = normalize(from_num, country)
    tmsg = client.messages.create(body=msg, to=to_num, from_=from_num)
    return tmsg


def find(text, country="US"):
    # finds any phone numbers in the text blob
    numbers = []
    for match in phonenumbers.PhoneNumberMatcher(text, country):
        numbers.append(normalize(match.number, country))
    return numbers


def isValid(number, country="US"):
    return phonenumbers.is_valid_number(phonenumbers.parse(number, country))


def normalize(raw_phone, country="US"):
    # turns a number like 202-413-2409 into +12024132409
    return convert_to_e164(raw_phone, country)


def convert_to_e164(raw_phone, country="US"):
    if not raw_phone:
        return

    if raw_phone[0] == '+':
        # Phone number may already be in E.164 format.
        parse_type = None
    else:
        # If no country code information present, assume it's a US number
        parse_type = country

    phone_representation = phonenumbers.parse(raw_phone, parse_type)
    return phonenumbers.format_number(
        phone_representation,
        phonenumbers.PhoneNumberFormat.E164)
