from sys import argv
from imp import load_source
import yaml
import argparse
from scalepot import do
from scalepot import ec2


def arg_parse():
    global _implemention_file_path, _config_file_path
    parser = argparse.ArgumentParser(description='scalepot v0.1')
    parser.add_argument('--implemention', '-i',
                        help='Your implemention file path. ' + \
                             'Default is ./scalepot.py',
                        type=str,
                        default='scalepot.py')
    parser.add_argument('--config', '-c',
                        help='Your config file path. ' + \
                             'Default is ./scalepot.yml',
                        type=str,
                        default='scalepot.yml')
    namespace = parser.parse_args(argv[1:])
    _implemention_file_path = namespace.implemention
    _config_file_path = namespace.config


def load_config(path):
    config_file = file(path, 'r')
    config = yaml.load(config_file)
    do.config.update(config)
    ec2.region_name = config['az']
    return config


def main():
    print 'scalepot v0.1'
    arg_parse()
    load_config(_config_file_path)
    load_source('implemention', _implemention_file_path)
    do.run_forever()
