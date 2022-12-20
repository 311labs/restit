import boto3
from datetime import datetime, timedelta
from django.conf import settings
from objict import objict
import socket


METRIC_MAP = {
    "ec2": "AWS/EC2",
    "rds": "AWS/RDS",
    "cpu": "CPUUtilization",
    "connections": "DatabaseConnections",
    "cons": "DatabaseConnections",
    "max": "Maximum",
    "min": "Minimum",
    "avg": "Average"
}


def getLocalEC2():
    """
    {
        "id": "i-0c50eec6fdf91dcaf",
        "image_id": "ami-035e0c65b8a27be8d",
        "name": "epoc.pauth.io",
        "private_ip": "172.31.49.79",
        "public_ip": "35.88.50.208",
        "security_groups": [ {
                "id": "sg-0e15d7c997b004458",
                "name": "epoc_server"
            }],
        "service": "unknown",
        "state": "running",
        "subnet_id": "subnet-e282b1ca",
        "type": "t3.medium",
        "vpc_id": "vpc-000e9565",
        "zone": "us-west-2d"
    }
    """
    hostname = socket.gethostname()
    priv_ip = socket.gethostbyname(hostname)
    return getEC2ByIP(priv_ip)


def getClient(region="us-west-2", service="cloudwatch"):
    key = settings.AWS_KEY
    secret = settings.AWS_SECRET
    return boto3.client(service, aws_access_key_id=key, aws_secret_access_key=secret, region_name=region)


def buildQuery(id, instance, period=300, metric="cpu", namespace="rds", stat="max"):
    dname = "DBInstanceIdentifier"
    if namespace == "ec2":
        dname = "InstanceId"
    mstat = dict(Namespace=METRIC_MAP.get(namespace, namespace), MetricName=metric)
    mstat["Dimensions"] = [dict(Name=dname, Value=instance)]
    return dict(Id=id, MetricStat=dict(Metric=mstat, Period=period, Stat=METRIC_MAP.get(stat, stat)))
    

def getMetrics(instances, period=300, duration_seconds=900, metric="cpu", namespace="rds", stat="max"):
    cloudwatch = getClient(service="cloudwatch")
    query = []
    id_to_instance = {}
    metric_query = METRIC_MAP.get(metric, metric)
    for i in instances:
        name = i.replace("-", "_")
        key = F"{name}_{metric}"
        id_to_instance[key] = i
        query.append(buildQuery(key, i, period, metric=metric_query, namespace=namespace, stat=stat))
    response = cloudwatch.get_metric_data(
        MetricDataQueries=query,
        StartTime=(datetime.now() - timedelta(seconds=duration_seconds)).timestamp(),
        EndTime=datetime.now().timestamp())
    if "MetricDataResults" in response:
        output = objict()
        for resp in response.get("MetricDataResults"):
            output[id_to_instance.get(resp.get("Id"), "unknown")] = resp.get("Values")
        return output
    return response


def getMetricsList(instance, namespace="rds"):
    dname = "DBInstanceIdentifier"
    if namespace == "ec2":
        dname = "InstanceId"
    cloudwatch = getClient(service="cloudwatch")
    response = cloudwatch.list_metrics(
        Namespace=METRIC_MAP.get(namespace, namespace),
        Dimensions=[dict(Name=dname, Value=instance)])
    metrics_list = response['Metrics']
    metrics_names = [metric['MetricName'] for metric in metrics_list]
    return metrics_names


def getAllEC2(region="us-west-2", just_ids=False):
    """
    This function returns a list with all EC2 instances in a region.
    """
    ec2_client = getClient(region=region, service="ec2")
    response = ec2_client.describe_instances()
    # log.prettyWrite(response)
    instances_reservation = response['Reservations']
    instances_description = []
    for res in instances_reservation:
        for instance in res['Instances']:
            instances_description.append(_normalizeEC2(instance))
    if not just_ids:
        return instances_description
    instances_id_list = []
    for instance in instances_description:
        instances_id_list.append(instance[0]['InstanceId'])
    return instances_id_list


def getEC2ByIP(ip):
    # retreives the local ec2 instance details by private ip
    client = getClient("ec2")
    filters = [dict(Name="private-ip-address", Values=[ip])]
    resp = client.describe_instances(Filters=filters)["Reservations"]
    try:
        details = resp[0]['Instances'][0]
    except Exception:
        return None
    return _normalizeEC2(details)


def _normalizeEC2(details):
    name = "unknown"
    service = "unknown"
    for tag in details["Tags"]:
        if tag["Key"] == "Name":
            name = tag["Value"]
        elif tag["Key"] == "Service":
            service = tag["Value"]
    info = objict(
        id=details["InstanceId"],
        image_id=details["ImageId"],
        type=details["InstanceType"],
        name=name,
        service=service,
        zone=details["Placement"]["AvailabilityZone"],
        public_ip=details["PublicIpAddress"],
        private_ip=details["PrivateIpAddress"],
        state=details["State"]["Name"],
        subnet_id=details["SubnetId"],
        vpc_id=details["VpcId"],
        security_groups=[]
    )
    for group in details["SecurityGroups"]:
        info.security_groups.append(dict(name=group["GroupName"], id=group["GroupId"]))
    return info
