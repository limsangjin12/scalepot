import gevent
from gevent.pool import Group
from werkzeug import LocalStack, LocalProxy
from scalepot.ec2 import (get_instances, cpu_utilization,
                          launch_instance, launch_spot_instance,
                          get_spot_request_by_id)
from scalepot.exceptions import *
from scalepot.utils import State, Role, ScaleInfo, AttributeDict


config = AttributeDict({
    'roles': None,
    'scale_func': None,
    'check_func': None,
    'region_name': None,
    'scale_out_threshold': 60,
    'scale_down_ratio': 0.7
})
_scale_ctx_stack = LocalStack()
g = LocalProxy(lambda: _scale_ctx_stack.top)


def check_cpu_utilization(role):
    instances = get_instances(role.name)
    value = cpu_utilization(instances)
    if value > config.scale_out_threshold:
        if role.max <= g.count:
            return State.MAX_LIMIT
        return State.SCALE_OUT
    elif value < config.scale_out_threshold * config.scale_down_ratio:
        if role.min > g.count:
            return State.SCALE_OUT
        elif role.min == g.count:
            return State.MIN_LIMIT
        return State.SCALE_DOWN
    return State.NORMAL


def action(role, state):
    info = ScaleInfo(role, state)
    if state == State.SCALE_OUT:
        if role.option == 'on-demand':
            info.instance = launch_instance(role)
        elif role.option == 'spot':
            info.instance = launch_spot_instance(role)
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
            for instance in get_instances(role.name):
                try:
                    instance.terminate()
                    if instance.spot_instance_request_id is not None:
                        spot_request_id = instance.spot_instance_request_id
                        get_spot_request_by_id(spot_request_id).cancel()
                    info.instance = instance.update()
                except:
                    continue
                else:
                    break
            else:
                raise ScaleError('Instance termination failed.' + \
                                 'Cannot scale-down.')
        else:
            raise ScaleError('Option ' + repr(role.option) + \
                             'does not exist.')
        info.state = State.SCALE_DOWN
    elif state == State.MAX_LIMIT:
        pass
    elif state == State.MIN_LIMIT:
        pass
    elif state == State.NORMAL:
        pass
    else:
        raise ScaleError('State ' + repr(state) + 'does not exist.')
    _scale_ctx_stack.push(info)
    config.scale_func()
    _scale_ctx_stack.pop()


def ready(role):
    queue = Group()
    while True:
        info = ScaleInfo(role)
        _scale_ctx_stack.push(info)
        if config.check_func is not None:
            queue.spawn(action, role, config.check_func())
        else:
            queue.spawn(action, role, check_cpu_utilization(role))
        queue.spawn(gevent.sleep, role.cooltime*60)
        queue.join()
        _scale_ctx_stack.pop()


def run_forever():
    role_queue = Group()
    for roledict in config.roles:
        role = Role(roledict)
        role_queue.spawn(ready, role)
    role_queue.join()
