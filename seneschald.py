# -*- coding: utf-8 -*-

"""Daemon control script. The seneschal daemon handles messages requesting
processing or export of data located within the protected area."""


import argparse
import logging
import logging.config
import os
import signal
import sys
import syslog
import time

from daemon import DaemonContext
from daemon.runner import is_pidfile_stale
from lockfile.pidlockfile import PIDLockFile
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
    try:
        if daemon_command == 'start':
            start(logging_config, daemon_config, seneschal_config)
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


def start(logging_config, daemon_config, seneschal_config):
    syslog.openlog('seneschal', 0, syslog.LOG_USER)
    pidfile, daemon_kwds = check_daemon_options(daemon_config)
    if is_pidfile_stale(pidfile):
        syslog.syslog(syslog.LOG_NOTICE, 'breaking stale PID file')
        pidfile.break_lock()
    # The remaining entries in daemon_kwds will be passed as-is to
    # daemon.DaemonContext.
    context = DaemonContext(pidfile=pidfile, **daemon_kwds)
    context.signal_map = make_signal_map()
    syslog.syslog(syslog.LOG_NOTICE, 'starting daemon context')
    try:
        with context:  # Will fail if daemon already running
            pid = os.getpid()
            syslog.syslog(syslog.LOG_NOTICE, 'daemon running as: %s' % pid)
            config_logging(logging_config)
            logger.debug('========================================')
            logger.info('daemon running pid=%s', pid)
            logger.debug('args: %r', sys.argv)
            logger.debug('daemon_kwds: %r', daemon_kwds)
            logger.debug('seneschal_config: %r', seneschal_config)
            while running:
                logger.debug('ping')
                syslog.syslog(syslog.LOG_NOTICE, 'ping from %s' % pid)
                time.sleep(1)
                # TODO: Long polling times, may result in an unacceptable
                # delay during daemon shutdown.
                # 1/0
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, str(e))
        logger.exception(repr(e))
        raise
    finally:
        syslog.syslog(syslog.LOG_NOTICE, 'exiting')
        logger.info('exiting')


def check_daemon_options(daemon_config):
    """Returns the pidfile object and non-default daemon settings;
    dies if there are any illegal settings."""
    check_for_illegal_daemon_options(daemon_config)
    daemon_kwds = {k: v for k, v in daemon_config.items() if v is not None}
    pidfile_path = daemon_kwds.pop('pidfile')
    pidfile = PIDLockFile(pidfile_path)
    return pidfile, daemon_kwds


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


def make_signal_map():
    result = {
        signal.SIGTERM: trigger_shutdown,
        signal.SIGHUP: None,
        signal.SIGTTIN: None,
        signal.SIGTTOU: None,
        signal.SIGTSTP: None,
    }
    return result


def config_logging(logging_config_dict):
    if logging_config_dict:
        config = dict(logging_config_dict,
                      version=1,
                      disable_existing_loggers=False)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=logging.NOTSET)


def trigger_shutdown(signum, frame):
    """Set global `running` to False, to trigger shutdown."""
    syslog.syslog(syslog.LOG_NOTICE, 'term signal')
    global running
    running = False


if __name__ == "__main__":
    main()
