import gevent
from datetime import timedelta
from datetime import datetime
from boto import ec2
from boto.ec2 import cloudwatch


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


def launch_instance(role, timeout=60, interval=5):
    conn = get_ec2_connection()
    resv = conn.run_instances(role.ami,
                              instance_type=role.type,
                              placement=_region_name + \
                                        role.placement)
    for instance in resv.instances:
        trial = timeout / interval
        while trial > 0:
            gevent.sleep(interval)
            instance.update()
            trial -= 1
        if instance.state != 'running':
            raise ScaleError('Timed out. Cannot launch instance.')
        instance.create_tags([instance.id],
                             {'Name': role.name,
                              'Role': role.name})
        return instance


def cpu_utilization(instances, minutes=10):
    conn = get_cloudwatch_connection()
    stat_sum = 0.0
    for instance in instances:
        stats = conn.get_metric_statistics(period = 60,
                    start_time = datetime.utcnow() - \
                                 timedelta(minutes=minutes+5),
                    end_time = datetime.utcnow(),
                    metric_name = 'CPUUtilization',
                    namespace = 'AWS/EC2',
                    statistics = ['Average'],
                    dimensions = {'InstanceId': instance.id})
        stat_sum += sum(stat['Average'] for stat in stats) / len(stats)
    return stat_sum / len(instances)
