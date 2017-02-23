# -*- coding: utf-8 -*-

"""Functions for the lifecycle of messages. The action code lives in other
modules."""


import logging


logger = logging.getLogger(__name__)


class Engine(object):
    """Object responsible for fetching messages and delegating to
    the business rules."""
    running = True  # When False, start shutting down.

    def __init__(self, config):
        self.__dict__.update(config)  # Absorb config

    def sweep(self):
        """Loop over work queue until it is exhausted, then return."""
        while Engine.running:
            did_work = self.do_one_mesage()
            if not did_work:
                logger.debug('no more work')
                break

    def do_one_mesage(self):
        """Check for incoming messages, and process the first. Return
        True if a message was found, False otherwise."""
        return False  # TODO
