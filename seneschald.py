# -*- coding: utf-8 -*-

"""Daemon control script. The seneschal daemon handles messages requesting
processing or export of data located within the protected area."""


import argparse
import logging
import logging.config

import foo

import daemon
import yaml

from seneschal import *


logger = logging.getLogger('seneschald')


def main():
    args = parse_args()
    config = load_config_file(args.config_file)
    config_logging(config.pop('logging', None))
    logger.debug('args: %r', vars(args))
    try:
        run(config)
    finally:
        logging.shutdown()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config_file', help='path to YAML file')
    parser.add_argument('daemon_command', choices=['start', 'stop'])
    args = parser.parse_args()
    return args


def load_config_file(config_file):
    with open(config_file) as fin:
        config = yaml.load(fin)
    return config


def config_logging(logging_config_dict):
    if logging_config_dict:
        config = dict(logging_config_dict,
                      version=1,
                      disable_existing_loggers=False)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=logging.NOTSET)


def run(config):
    logger.debug('config: %r', config)
    logger.debug('========================================')


if __name__ == "__main__":
    main()
