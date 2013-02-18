from scalepot.do import config


def scale(func):
    if config.scale_func is None:
        config.scale_func = func
    else:
        raise ScaleError('Scaling function is already exist.')
    return func


def check(func):
    if config.check_func is None:
        config.check_func = func
    else:
        raise ScaleError('Scale-check function is already exist.')
    return func
