from gevent.pool import Group
from werkzeug import LocalStack, LocalProxy
from scalepot.ec2 import get_instances, cpu_utilization, launch_instance
from scalepot.exceptions import *
from scalepot.utils import State, Role, ScaleInfo, AttributeDict, get_roledict_by_name


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
