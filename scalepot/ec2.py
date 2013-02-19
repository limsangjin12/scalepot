import gevent
from datetime import timedelta
from datetime import datetime
from boto import ec2
from boto.ec2 import cloudwatch
from scalepot.exceptions import *


region_name = None
_ec2_conn = None
_cloudwatch_conn = None


def get_ec2_connection():
    global _ec2_conn
    if _ec2_conn is None:
        _ec2_conn = ec2.connect_to_region(region_name)
    return _ec2_conn


def get_cloudwatch_connection():
    global _cloudwatch_conn
    if _cloudwatch_conn is None:
        _cloudwatch_conn = cloudwatch.connect_to_region(region_name)
    return _cloudwatch_conn


def get_instances(rolename=None):
    conn = get_ec2_connection()
    reservations = conn.get_all_instances()
    instances = [inst for resv in reservations
                          for inst in resv.instances
                              if inst.state == 'running']
    if rolename is not None:
        instances = [inst for inst in instances
                              if inst.tags.get('Role') == rolename]
    return instances


def get_instance_by_id(id):
    conn = get_ec2_connection()
    reservations = conn.get_all_instances([id])
    for resv in reservations:
        for instance in resv.instances:
            return instance


def wait_for_run(instance, timeout=60, interval=5):
    trial = timeout / interval
    for _ in xrange(trial):
        gevent.sleep(interval)
        instance.update()
        if instance.state == 'running':
            break
    else:
        instance.terminate()
        raise ScaleError('Timed out. Cannot launch instance.')
    return instance


def launch_instance(role):
    conn = get_ec2_connection()
    resv = conn.run_instances(role.ami,
                              instance_type=role.type,
                              placement=_region_name + \
                                        role.placement)
    for instance in resv.instances:
        wait_for_run(instance)
        conn.create_tags([instance.id],
                         {'Name': role.name,
                          'Role': role.name})
        instance.update()
        return instance


def get_spot_request_by_id(id):
    conn = get_ec2_connection()
    requests = conn.get_all_spot_instance_requests([id])
    for request in requests:
        return request


def spot_price(role, hours=6):
    conn = get_ec2_connection()
    prices = conn.get_spot_price_history(
                start_time=(datetime.utcnow() - \
                            timedelta(hours=hours)).isoformat(),
                end_time=datetime.utcnow().isoformat(),
                instance_type=role.type,
                product_description='Linux/UNIX',
                availability_zone=region_name+role.placement)
    return sum(price.price for price in prices) / len(prices)


def wait_for_fulfill(request, timeout=300, interval=15):
    trial = timeout / interval
    for _ in xrange(trial):
        gevent.sleep(interval)
        request = get_spot_request_by_id(request.id)
        if request.state == 'active':
            break
    else:
        request.cancel()
        raise ScaleError('Timed out. Cannot launch spot instance.')
    return request


def launch_spot_instance(role):
    conn = get_ec2_connection()
    price = spot_price(role) * 3
    requests = conn.request_spot_instances(
                price=price,
                image_id=role.ami,
                count=1,
                instance_type=role.type,
                placement=region_name+role.placement)
    for request in requests:
        request = wait_for_fulfill(request)
        instance = get_instance_by_id(request.instance_id)
        wait_for_run(instance)
        conn.create_tags([instance.id],
                         {'Name': role.name,
                          'Role': role.name})
        instance.update()
        return instance


def cpu_utilization(instances, minutes=10):
    conn = get_cloudwatch_connection()
    stat_sum = 0.0
    for instance in instances:
        stats = conn.get_metric_statistics(
                    period=60,
                    start_time=datetime.utcnow() - \
                               timedelta(minutes=minutes+5),
                    end_time=datetime.utcnow(),
                    metric_name='CPUUtilization',
                    namespace='AWS/EC2',
                    statistics=['Average'],
                    dimensions={'InstanceId': instance.id})
        if stats:
            stat_sum += sum(stat['Average'] for stat in stats) / len(stats)
        else:
            raise ScaleError('Stat semms empty.')
    return stat_sum / len(instances)
