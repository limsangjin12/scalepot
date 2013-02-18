from scalepot.ec2 import get_instances


class AttributeDict(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


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
        setattr_dict(self, roledict)


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


def get_roledict_by_name(rolename):
    for roledict in config.roles:
        if roledict['name'] == rolename:
            return roledict
    return None


def setattr_dict(obj, dict_):
    for key in dict_.iterkeys():
        setattr(obj, key, dict_[key])


def sort_with_timestamp(items):
    return items.sort(key=lambda item:item['Timestamp'])
