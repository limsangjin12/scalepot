import argparse
import api
import yaml


def import_scalefile():
    # find and import scalefile module here
    import scalefile


def arg_parse():
    parser = argparse.ArgumentParser(description='scalepot v0.1')


def load_config():
    config = file('scalepot.yml', 'r')
    return yaml.load(config)


def print_iter(obj):
    if type(obj) == dict:
        for o in obj.iterkeys():
            print '<'+o+'>'
            print_iter(obj[o])
    elif type(obj) == list or \
       type(obj) == tuple or \
       type(obj) == set:
        for o in obj:
            print_iter(o)
    else:
        print obj


def main():
    print 'scalepot v0.1'
    import_scalefile()
    arg_parse()

    # setup configuration
    config = load_config()
    api._roles = config['roles']
    api._region_name = config['az']
    api._scale_out_threshold = config['scale-out-threshold']
    api._scale_down_ratio = config['scale-down-ratio']
    print_iter(config)
    print '----------------------'

    # check and scale
    api.check()


if __name__ == '__main__':
    main()
