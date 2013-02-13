from datetime import timedelta
from datetime import datetime
from boto import ec2
from boto.ec2 import cloudwatch


_roles = set()
_scale_out_func = {}
_scale_down_func = {}
_scale_cond = {}
_ec2_conn = None
_cloudwatch_conn = None

_region_name = 'ap-northeast-1'
_scale_out_threshold = 60
_scale_down_ratio = 0.7


class NoScalingFunctionError(Exception):
    pass


class State(object):
    SCALE_OUT = 'SCALEOUT'
    SCALE_DOWN = 'SCALEDOWN'
    NORMAL = 'NORMAL'


def scale_out(*roles):
    for role in roles:
        _roles.add(role)
    def register(func):
        for role in roles:
            _scale_out_func[role] = func
        return func
    return register


def scale_down(*roles):
    for role in roles:
        _roles.add(role)
    def register(func):
        for role in roles:
            _scale_down_func[role] = func
        return func
    return register


def scale_check(*roles):
    def register(func):
        for role in roles:
            _scale_cond[role] = func
        return func
    return register


def get_ec2_connection():
    global _ec2_conn
    if _ec2_conn is None:
        _ec2_conn = ec2.connect_to_region(_region_name)
    return _ec2_conn


def get_cloudwatch_connection():
    global _cloudwatch_conn
    if _cloudwatch_conn is None:
        _cloudwatch_conn = cloudwatch.connect_to_region(_region_name)
    return _cloudwatch_conn


def get_instances(role=None):
    conn = get_ec2_connection()
    reservations = conn.get_all_instances()
    instances = [inst for resv in reservations
                          for inst in resv.instances
                              if inst.state == 'running']
    if role is not None:
        instances = [inst for inst in instances
                              if inst.tags.get('Purpose') == role]
    return instances


def sort_with_timestamp(items):
    return items.sort(key=lambda item:item['Timestamp'])


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


def check_cpu_utilization(role):
    region = get_ec2_connection()
    instances = get_instances(role)
    value = cpu_utilization(instances)
    print value
    if value  > _scale_out_threshold:
        return State.SCALE_OUT
    elif value < _scale_out_threshold * _scale_down_ratio:
        return State.SCALE_DOWN
    return State.NORMAL


def scale(role, state):
    if state == State.SCALE_OUT:
        print 'scale_out'
        if role in _scale_out_func:
            # launch spot instance here
            instance = None
            _scale_out_func[role](instance)
        else:
            raise NoScalingFunctionError('scale_out function ' +
                                         'must be defined.')
    elif state == State.SCALE_DOWN:
        print 'scale_down'
        if role in _scale_down_func:
            # terminate spot instance here
            instance = None
            _scale_down_func[role](instance)
        else:
            raise NoScalingFunctionError('scale_down function ' +
                                         'must be defined.')
    else:
        print 'normal'


def check():
    for role in _roles:
        if role in _scale_cond:
            scale(role, _scale_cond[role]())
        else:
            scale(role, check_cpu_utilization(role))

