"""JSON file based messaging. User client software makes requests by executing
`leave_new_request`. The rest of this module supports the automation engine."""

from json import dump, load
import logging
from pathlib import Path
from uuid import uuid4

from .exceptions import SeneschalError


# TODO: Start auditing messages.

# Channels
REQUEST = 'REQUEST'
JOB = 'JOB'
SUBPROCESS = 'SUBPROCESS'

# MessageDrop directory names
TEMP = '0_temp'
INBOX = '1_inbox'
RECEIVED = '2_received'
ERROR = '3_error'

# Message types
NEW = 'NEW'
STARTED = 'STARTED'
SUCCEEDED = 'SUCCEEDED'
FAILED = 'FAILED'

# JSON message keys
ILLEGAL_JSON_KEYS = {'channel', 'uid', 'user_name'}
REQUIRED_JSON_KEYS = {'message_type', 'target_id', 'uuid_str'}


logger = logging.getLogger(__name__)


def leave_new_request(directory, workflow, arg_list):
    """On behalf of a user, creates a new Request message file, using
    `directory` as the root of a message drop. The requested automation is
    named by `workflow`. This is the only code in this module that client
    software needs to invoke in order to create a request."""
    uuid_str = leave_message(directory, NEW,
                             workflow=workflow, arg_list=arg_list)
    return uuid_str


class Message:
    """Contains a single message as a JSON file. `channel` is where the message
    should go. `target_id` is the ID of a specific object that should get the
    message. `message_type` defines the general type of the message. Any
    additional attributes are specific to the type of message."""
    def __init__(self, *, channel, target_id, message_type, **kwds):
        self.channel = channel
        self.target_id = target_id
        self.message_type = message_type
        self.__dict__.update(kwds)
        # TODO: Make explicit uid, user_name, uuid_str.


class MessageBroker:
    """Responsible for creating, receiving, and dispatching messages, which
    are serialized as JSON files."""
    def __init__(self, seneschal_config):
        self.job_events_path = seneschal_config['paths']['job_events']
        self.user_events_path = seneschal_config['paths']['user_events']
    # TODO


class MessageDrop(object):
    """Represents a filesystem directory that contains a `TEMP` directory and
    an `INBOX` directory. Messages are placed in the drop by writing a new
    JSON file with a unique name to the `TEMP` directory and then moving that
    file to the `INBOX` directory. Messages left here should not contain uid,
    user_name, or channel. When messages are read back into memory, they are
    augmented with these values. The user is the owner of the file."""
    def __init__(self, *, directory, channel, **kwds):
        """Parameters: `directory` must contain `TEMP`, `INBOX`, and `RECEIVED`;
        `channel` is only used when fetching messages."""
        super().__init__(**kwds)
        self.directory = Path(directory)
        self.channel = channel

    @property
    def inbox(self):
        """Returns `self.directory / INBOX`."""
        return self.directory / INBOX

    @property
    def received(self):
        """Returns `self.directory / RECEIVED`."""
        return self.directory / RECEIVED

    @property
    def error(self):
        """Returns `self.directory / ERROR`."""
        return self.directory / ERROR

    def leave_message(self, message_type, target_id=None, **kwds):
        """Write a new JSON file into the `TEMP` directory and then move that
        file into the `INBOX` directory. The JSON file is an object (dict)
        that contains the combination of message_type, target_id, kwds, and
        a UUID, which is also used to name the file. The UUID is generated
        inside this method using `uuid4`, so as to insure that the message and
        file have unique names. Returns the UUID as a str. This method is
        usually invoked from client software that does not call any other
        methods in this module."""
        # TODO: Consider that we may want to create a UUID based on a previous
        # UUID, such as events for an existing job or request, using a
        # UUID5 algorith taking the existing UUID as the namespace.
        leave_message(self.directory, message_type, target_id, **kwds)

    def fetch_message(self):
        """Return the next message or `None`. Locates the oldest JSON file in
        the `INBOX` directory, loads it, moves it into the `RECEIVED`
        directory, and returns the resulting `Message` object."""
        message_paths = sorted(self.inbox.glob('*.json'),
                               key=lambda x: x.stat().st_mtime)
        if message_paths:
            message_path = message_paths[0]
            name = message_path.name
            try:
                message = load_message(message_path, self.channel)
            except ValueError as e:
                logger.exception(f'problem loading {name}')
                message_path.rename(self.error / name)
                message = None
            else:
                message_path.rename(self.received / name)
        else:
            message = None
        return message


def load_message(message_path, channel):
    """Return the `Message` object at message_path, filling in `channel`,
    `uid`, and `user_name`. Will raise a subclass of `ValueError` if the file
    has a bad set of keys or the UUID in the file does not match the name of
    the file."""
    message_path = Path(message_path)
    with message_path.open() as fin:
        message_mapping = load(fin)
    message_keys = set(message_mapping)
    illegal_keys = ILLEGAL_JSON_KEYS & message_keys
    missing_keys = REQUIRED_JSON_KEYS - message_keys
    if illegal_keys:
        raise IllegalJSONKeysError(
            f'illegal keys in {message_path.name}: {illegal_keys}'
        )
    if missing_keys:
        raise IllegalJSONKeysError(
            f'missing keys in {message_path.name}: {missing_keys}'
        )
    message = Message(channel=channel, 
                      uid=message_path.stat().st_uid,
                      user_name=message_path.owner(),
                      **message_mapping)
    if message.uuid_str != message_path.stem:
        raise ValueError(
            f'wrong UUID in {message_path.name}: {message.uuid_str}'
        )
    return message


def leave_message(directory, message_type, target_id=None, **kwds):
    """Using `directory` as the root of a message drop, write a new JSON file
    into the `TEMP` directory and then move that file into the `INBOX`
    directory. The JSON file is an object (dict) that contains the combination
    of message_type, target_id, kwds, and a UUID, which is also used to name
    the file. The UUID is generated inside this method using `uuid4`, so as to
    insure that the message and file have unique names. Returns the UUID as a
    str. This function is usually invoked from client software that does not
    call anything else in this module."""
    assert 'uuid_str' not in kwds, kwds
    assert 'channel' not in kwds, kwds  # TODO: FIX THIS LIST.
    directory_path = Path(directory)
    uuid_str = str(uuid4())
    file_name = uuid_str + '.json'
    initial_path = directory_path / TEMP / file_name
    final_path = directory_path / INBOX / file_name
    message = dict(uuid_str=uuid_str,
                   message_type=message_type,
                   target_id=target_id,
                   **kwds)
    with initial_path.open('w') as fout:
        dump(message, fout, sort_keys=True)
    initial_path.rename(final_path)
    return uuid_str


class MissingJSONKeysError(ValueError):
    """Some required keys were missing."""
    pass


class IllegalJSONKeysError(ValueError):
    """Some illegal keys were present in a JSON file."""
    pass
