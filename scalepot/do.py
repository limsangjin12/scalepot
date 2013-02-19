from gevent.pool import Group
from werkzeug import LocalStack, LocalProxy
from scalepot.ec2 import (get_instances, cpu_utilization,
                          launch_instance, launch_spot_instance,
                          get_spot_request_by_id)
from scalepot.exceptions import *
from scalepot.utils import (State, Role, ScaleInfo,
                            AttributeDict, get_roledict_by_name)


config = AttributeDict({
    'roles': None,
    'scale_func': None,
    'check_func': None,
    'region_name': None,
    'scale_out_threshold': 60,
    'scale_down_ratio': 0.7
})
_scale_queue = Group()
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
        if role.min >= g.count:
            return State.MIN_LIMIT
        return State.SCALE_DOWN
    return State.NORMAL



def action(role, state):
    info = ScaleInfo(role, state)
    if state == State.SCALE_OUT:
        if role.option == 'on-demand':
            instance = launch_instance(role)
            info.instance = instance
        elif role.option == 'spot':
            instance = launch_spot_instance(role)
            info.instance = instance
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
    info = ScaleInfo(role)
    _scale_ctx_stack.push(info)
    if config.check_func is not None:
        action(role, config.check_func())
    else:
        action(role, check_cpu_utilization(role))
    _scale_ctx_stack.pop()


def tick(rolename=None):
    if rolename is None:
        for roledict in config.roles:
            role = Role(roledict)
            _scale_queue.spawn(ready, role)
    else:
        role = Role(get_roledict_by_name(rolename))
        _scale_queue.spawn(ready, role)
    _scale_queue.join()
