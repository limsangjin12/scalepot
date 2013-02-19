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


class Role(AttributeDict):
    pass


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
