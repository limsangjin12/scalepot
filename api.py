from datetime import timedelta
from datetime import datetime
from boto import ec2
from boto.ec2 import cloudwatch
from werkzeug import LocalStack, LocalProxy
import gevent
from gevent.pool import Group


_roles = None
_scale_func = None
_scale_check_func = None
_ec2_conn = None
_cloudwatch_conn = None
_region_name = None
_scale_out_threshold = 60
_scale_down_ratio = 0.7

_scale_queue = Group()
_scale_ctx_stack = LocalStack()
g = LocalProxy(lambda: _scale_ctx_stack.top)


class ScaleError(Exception):
    pass


class State(object):
    SCALE_OUT = 'SHOULD SCALE OUT'
    SCALE_DOWN = 'SHOULD SCALE DOWN'
    MAX_LIMIT = 'MAX LIMIT REACHED'
    MIN_LIMIT = 'MIN LIMIT REACHED'
    NORMAL = 'NORMAL'

    def __contains__(self, key):
        # must be implemented
        pass


class Role(object):
    def __init__(self, roledict):
        # validate arguments here
        for key in roledict.iterkeys():
            setattr(self, key, roledict[key])


class ScaleInfo(object):
    def __init__(self, role, state=None, instance=None, count=None):
        # validate arguments here
        self.role = role
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
        raise ScaleError('Scaling function is already exist.')
    return func


def scale_check(func):
    global _scale_check_func
    if _scale_check_func is None:
        _scale_check_func = func
    else:
        raise ScaleError('Scale-check function is already exist.')
    return func


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
                              if inst.tags.get('Role') == role]
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
    instances = get_instances(role.name)
    value = cpu_utilization(instances)
    if value > _scale_out_threshold:
        if role.max <= role.count:
            return State.MAX_LIMIT
        return State.SCALE_OUT
    elif value < _scale_out_threshold * _scale_down_ratio:
        if role.min >= role.count:
            return State.MIN_LIMIT
        return State.SCALE_DOWN
    return State.NORMAL


def launch_instance(role, timeout=60, interval=5):
    conn = get_ec2_connection()
    resv = conn.run_instances(role.ami,
                              instance_type=role.type,
                              placement=_region_name + \
                                        role.placement)
    for instance in resv.instances:
        trial = 0
        while instance.state != 'running':
            gevent.sleep(interval)
            instance.update()
            trial++
            if trial * interval > timeout:
                raise ScaleError('Cannot launch instance.')
        instance.create_tags([instance.id],
                             {'Name': role.name,
                              'Role': role.name})
        return instance


def action(role, state):
    # validate state here
    info = ScaleInfo(role)
    if state == State.SCALE_OUT:
        if role.option == 'on-demand':
            try:
                instance = launch_instance(role)
            except:
                raise ScaleError('Cannot launch instance.')
            else:
                info.instance = instance
                info.state = State.SCALE_OUT
        elif role.option == 'spot':
            raise NotImplementedError('Must be implemented spot-scaling.')
        else:
            raise ScaleError('Option ' + repr(role.option) + \
                             'does not exist')
    elif state == State.SCALE_DOWN:
        if role.option == 'on-demand':
            for instance in get_instances(role.name):
                try:
                    instance.terminate()
                except:
                    continue
                else:
                    break
            else:
                raise ScaleError('Instance termination failed.' + \
                                 'Cannot scale-down.')
        elif role.option == 'spot':
            raise NotImplementedError('Must be implemented spot-scaling.')
        else:
            raise ScaleError('Option ' + repr(role.option) + \
                             'does not exist.')
        info.state = State.SCALE_DOWN
    elif state == State.MAX_LIMIT:
        info.state = State.MAX_LIMIT
    elif state == State.MIN_LIMIT:
        info.state = State.MIN_LIMIT
    elif state == State.NORMAL:
        info.state = State.NORMAL
    else:
        raise ScaleError('State ' + repr(state) + 'does not exist.')
    _scale_ctx_stack.push(info)
    _scale_func()
    _scale_ctx_stack.pop()


def ready(role):
    info = ScaleInfo(role)
    _scale_ctx_stack.push(info)
    if _scale_check_func is not None:
        action(role, _scale_check_func())
    else:
        action(role, check_cpu_utilization(role))
    _scale_ctx_stack.pop()


def check():
    for roledict in _roles:
        role = Role(roledict)
        _scale_queue.spawn(ready, role)
    _scale_queue.join()
