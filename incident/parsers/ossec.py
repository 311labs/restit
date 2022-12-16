from objict import objict
from datetime import datetime
import re
from .. import models as am
from location.models import GeoIP

IGNORE_RULES = [
    "100020"
]

LEVEL_REMAP_BY_RULE = {
    5402: 7,
    5710: 5
}


def parseAlert(request, data):
    # helpers.log_print(data)
    data = objict.fromJSON(data.replace('\n', '\\n'))
    for key in data:
        data[key] = data[key].strip()

    if data.rule_id in IGNORE_RULES:
        return None
    if "test" in data.hostname and data.rule_id == "533":
        # bug on test ossec falsely report 533 events
        return None
    if data.rule_id == "510" and "/dev/.mount/utab" in data.text:
        return None
    # we care not for this field for now
    data.pop("logfile", None)
    if not data.text:
        raise Exception("invalid or missing json")
    alert = am.ServerOssecAlert(**data)
    alert.when = datetime.utcfromtimestamp(int(data.alert_id[:data.alert_id.find(".")]))
    # now lets parse the title
    title = alert.text[alert.text.find("Rule:") + 5:]
    # level to int
    level = title[title.find('(level') + 7:]
    alert.level = int(level[:level.find(')')].strip())
    title = title[:title.find('\n')].strip()
    pos = title.find("->")
    if pos > 0:
        title = title[pos + 2:]
    alert.title = title

    if data.hostname == "test":
        if data.rule_id == "31120" or "Web server" in title:
            return None

    # helpers.log_print(title, alert.title)
    # source ip (normally public ip of host)
    pos = alert.text.find("Src IP:")
    if pos > 1:
        src_ip = alert.text[alert.text.find("Src IP:") + 7:]
        alert.src_ip = src_ip[:src_ip.find('\n')].strip()

    irule = int(alert.rule_id)
    if irule == 5710:
        m = re.search(r"Invalid user (\S+) from (\S+)", data.text)
        if m and m.groups():
            alert.username = m.group(1)
            alert.src_ip = m.group(2)
        else:
            m = re.search(r"Invalid user  from (\S+)", data.text)
            if m and m.groups():
                alert.username = "(empty string)"
                alert.src_ip = m.group(1)
    elif irule == 2932:
        m = re.search(r"Installed: (\S+)", data.text)
        if m and m.groups():
            package = m.group(1)
            alert.title = "Yum Package Installed: {}".format(package)
    elif irule == 551:
        # Integrity checksum changed for: '/etc/ld.so.cache'
        m = re.search(r"Integrity checksum changed for: '(\S+)'", data.text)
        if m and m.groups():
            action = m.group(1)
            alert.title = "File Changed: {}".format(action)
    elif irule == 5715:
        m = re.search(r"Accepted publickey for (\S+).*ssh2: ([^\n\r]*)", data.text)
        if m and m.groups():
            ssh_sig = m.group(2)
            if " " in ssh_sig:
                kind, ssh_sig = ssh_sig.split(' ')
            alert.username = m.group(1)
            alert.ssh_sig = ssh_sig
            alert.ssh_king = kind
            alert.title = f"SSH LOGIN:{alert.username}@{alert.hostname} - {ssh_sig}"
            # member = findUserBySshSig(ssh_sig)
            # if member:
            #     alert.title = "SSH LOGIN user: {}".format(member.username)
    elif irule == 5501:
        # pam_unix(sshd:session): session opened for user git by (uid=0)
        m = re.search(r"session (\S+) for user (\S+)*", data.text)
        if m and m.groups():
            alert.action = m.group(1)
            alert.username = m.group(2)
            alert.title = f"session {alert.action} for user {alert.username}"
    elif irule == 5402:
        # TTY=pts/0 ; PWD=/opt/mm_protector ; USER=root ; COMMAND=/sbin/iptables -F
        m = re.search(r"sudo:\s*(\S+).*COMMAND=([^\n\r]*)", data.text)
        if m and m.groups():
            alert.username = m.group(1)
            alert.title = "sudo {}".format(m.group(2))
    elif irule == 5706:
        m = re.search(r"identification string from (\S+) port (\S+)", data.text)
        if m and m.groups():
            alert.src_ip = m.group(1)
    elif irule == 100020:
        m = re.search(r"\[(\S+)\]", data.text)
        if m and m.groups():
            alert.src_ip = m.group(1)

    if alert.src_ip != None and len(alert.src_ip) > 6:
        # lets do a lookup for the src
        alert.geoip = GeoIP.lookup(alert.src_ip)
    # finally here we change the alert level
    if irule in LEVEL_REMAP_BY_RULE:
        alert.level = LEVEL_REMAP_BY_RULE[irule]
    alert.save()
    return alert

