# -*- coding: utf-8 -*-

"""Daemon control script. The seneschal daemon handles messages requesting
processing or export of data located within the protected area."""


import argparse
import logging
import logging.config
import signal
import sys
import time

import foo

import daemon
import lockfile
import yaml

from seneschal import *


logger = logging.getLogger('seneschald')
running = True  # When False, will exit polling loop.


def main():
    args = parse_args()
    daemon_command = args.daemon_command
    config = load_config_file(args.config_file)
    logging_config = config.pop('logging', None)
    daemon_config = config.pop('daemon')
    seneschal_config = config.pop('seneschal')
    config_logging(logging_config)
    logger.debug('args: %r', vars(args))
    try:
        if daemon_command == 'start':
            start(daemon_command, daemon_config, seneschal_config)
        elif daemon_config == 'stop':
            pass  # TODO
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


def start(daemon_command, daemon_config, seneschal_config):
    logger.debug('daemon_config: %r', daemon_config)
    logger.debug('seneschal_config: %r', seneschal_config)
    logger.debug('========================================')
    check_for_illegal_daemon_options(daemon_config)
    daemon_kwds = {k: v for k, v in daemon_config.items() if v is not None}
    pidfile_path = daemon_kwds.pop('pidfile')
    pidfile = lockfile.FileLock(pidfile_path)
    # TODO: check for already running process
    logger.debug('daemon_kwds: %r', daemon_kwds)
    # The remaining entries in daemon_kwds will be passed as-is to
    # daemon.DaemonContext.
    context = daemon.DaemonContext(pidfile=pidfile, **daemon_kwds)
    context.signal_map = {
        signal.SIGTERM: trigger_shutdown,
        signal.SIGHUP: None,
        signal.SIGTTIN: None,
        signal.SIGTTOU: None,
        signal.SIGTSTP: None,
    }
    logger.info('starting daemon context')
    with context:
        while running:
            logger.info('ping')
            time.sleep(0.5)
            # TODO: Long polling times, may result in an unacceptable
            # delay during daemon shutdown.


def check_for_illegal_daemon_options(daemon_config):
    """Error out and die if any illegal options."""
    LEGAL_DAEMON_OPTIONS = set('''
        pidfile
        working_directory
        chroot_directory
        umask
        detach_process
        uid
        gid
        prevent_core
    '''.split())
    illegal_options = set(daemon_config) - LEGAL_DAEMON_OPTIONS
    if illegal_options:
        logger.critical('illegal daemon options in YAML config file: %r',
                        list(illegal_options))
        sys.exit(1)


def trigger_shutdown(signum, frame):
    """Set global running to False, to trigger shutdown."""
    global running
    running = False


if __name__ == "__main__":
    main()
