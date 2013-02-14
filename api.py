from datetime import timedelta
from datetime import datetime
from boto import ec2
from boto.ec2 import cloudwatch
from werkzeug import LocalStack, LocalProxy
import gevent
from gevent.pool import Group
import collections


_roles = []
_scale_func = None
_scale_check_func = {}
_ec2_conn = None
_cloudwatch_conn = None

_region_name = 'ap-northeast-1'
_scale_out_threshold = 60
_scale_down_ratio = 0.7

_scale_queue = Group()
_scale_ctx_stack = LocalStack()
scaleinfo = LocalProxy(lambda: _scale_ctx_stack.top)


class FrozenDict(collections.Mapping):
    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        return hash(tuple(sorted(self._d.iteritems())))


class NoScalingFunctionError(Exception):
    pass


class State(object):
    SCALE_OUT = 'SHOULD SCALE OUT'
    SCALE_DOWN = 'SHOULD SCALE DOWN'
    MAX_LIMIT = 'MAX LIMIT REACHED'
    NORMAL = 'NORMAL'


class Role(object):
    def __init__(self, roledict):
        for key in roledict.iterkeys():
            setattr(self, key, roledict[key])


class ScaleInfo(object):
    def __init__(self, roledict, state=None, instance=None, count=None):
        self.role = Role(roledict)
        self.state = state
        self.instance = instance
        self._count = count

    @property
    def count(self):
        if self._count is None:
            instances = get_instances(self.role.name)
            self._count = len(instances)
        return self._count


def scale(func):
    global _scale_func
    if _scale_func is None:
        _scale_func = func
    else:
        raise Exception('scaling function is already exist')
    return func


def scale_check(*roles):
    global _scale_check_func
    def register(func):
        for role in roles:
            _scale_check_func[role] = func
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
    instances = get_instances(role['name'])
    value = cpu_utilization(instances)
    if value  > _scale_out_threshold:
        return State.SCALE_OUT
    elif value < _scale_out_threshold * _scale_down_ratio:
        return State.SCALE_DOWN
    return State.NORMAL


def action(role, state):
    info = ScaleInfo(role)
    if state == State.SCALE_OUT:
        if _scale_func is not None:
            # launch instance here
            info.state = State.SCALE_OUT
        else:
            raise NoScalingFunctionError('scale_out function ' +
                                         'must be defined.')
    elif state == State.SCALE_DOWN:
        if _scale_func is not None:
            # terminate instance here
            info.state = State.SCALE_DOWN
        else:
            raise NoScalingFunctionError('scale_down function ' +
                                         'must be defined.')
    elif state == State.MAX_LIMIT:
        info.state = State.MAX_LIMIT
    elif state == State.NORMAL:
        info.state = State.NORMAL
    else:
        raise Exception('there is no state ' + repr(state))
    _scale_ctx_stack.push(info)
    _scale_func()
    _scale_ctx_stack.pop()


def ready(role):
    info = ScaleInfo(role)
    _scale_ctx_stack.push(info)
    if role in _scale_check_func:
        action(role, _scale_check_func[role]())
    else:
        action(role, check_cpu_utilization(role))
    _scale_ctx_stack.pop()


def check():
    for role in _roles:
        _scale_queue.spawn(ready, FrozenDict(role))
    _scale_queue.join()
