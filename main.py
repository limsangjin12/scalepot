from sys import argv
from imp import load_source
import yaml
import argparse
import do
import ec2
from utils import setattr_dict


def arg_parse():
    global _implemention_file_path, _config_file_path
    parser = argparse.ArgumentParser(description='scalepot v0.1')
    parser.add_argument('--file', '-f',
                        help='Your implemention file path. ' + \
                             'Default is ./scalepot.py',
                        type=str,
                        default='./scalepot.py')
    parser.add_argument('--config', '-c',
                        help='Your config file path. ' + \
                             'Default is ./scalepot.yml',
                        type=str,
                        default='./scalepot.yml')
    namespace = parser.parse_args(argv[1:])
    _implemention_file_path = namespace.file
    _config_file_path = namespace.config


def load_config(path):
    config_file = file(path, 'r')
    config = yaml.load(config_file)
    setattr_dict(do.config, config)
    ec2.region_name = config['az']
    return config


def main():
    print 'scalepot v0.1'
    arg_parse()
    load_config(_config_file_path)
    load_source('implemention_part', _implemention_file_path)
    do.tick()


if __name__ == '__main__':
    main()
