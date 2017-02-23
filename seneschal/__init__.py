# -*- coding: utf-8 -*-

"""Engine for handling messages that represent requests to process
protected data. A request is a JSON file that contains:

1. the desired action
2. the input data
3. the destination
4. (optional) parameters

The owner of the the file is considered the sender of the message.

The lifecycle of a message:

1. User invokes a command that:
    a. writes the message in a temporary directory on the same filesystem as
       the queue directory
    b. moves the message to the queue directory
2. Automation (daemon):
    a. Select the oldest message in the queue.
    b. Move the message to the processing directory.
    c. Log the message.
    d. Apply business rules.
    e. Execute and log the action.
    f. Move the message the the finished directory.
3. Cleanup automation (crontab):
    a. Creates a new directory named after a time period.
    b. Moves all messages in the finished directory into the new directory.
    c. Creates a tarball based on the new directory.
    d. Verifies the tarball.
    e. Deletes the new directory and its contents.

Some messages simply result in sending a request for human approval. The
arrival of such an approval, triggers the matching requested action.
"""

from .engine import Engine


__author__ = """Walker Hale IV"""
__email__ = 'walker.hale.iv@gmail.com'
__version__ = '0.1.0'

__all__ = ['__author__', '__email__', '__version__', 'Engine']
