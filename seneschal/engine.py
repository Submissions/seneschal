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
