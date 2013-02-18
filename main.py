import argparse
import yaml
import do
import ec2


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
    do.config.roles = config['roles']
    do.config.scale_out_threshold = config['scale-out-threshold']
    do.config.scale_down_ratio = config['scale-down-ratio']
    ec2.region_name = config['az']
    print_iter(config)
    print '----------------------'

    # check and scale
    do.tick()


if __name__ == '__main__':
    main()
