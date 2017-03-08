"""JSON file based messaging."""

from json import dump, load
from pathlib import Path
from uuid import uuid4


# Channels
REQUEST = 'REQUEST'
JOB = 'JOB'
SUBPROCESS = 'SUBPROCESS'

# Message types
NEW = 'NEW'
STARTED = 'STARTED'
SUCCEEDED = 'SUCCEEDED'
FAILED = 'FAILED'

# Directory names
TEMP = '0_temp'
INBOX = '1_inbox'


class MessageBroker:
    """Responsible for creating, receiving, and dispatching messages, which
    are serialized as JSON files."""
    def __init__(self, seneschal_config):
        self.job_events_path = seneschal_config['paths']['job_events']
        self.user_events_path = seneschal_config['paths']['user_events']

    def send_new_request(self, workflow, arg_list):
        """On behalf of a user, creates a new Request message file."""
        message = NewRequestMessage(workflow, arg_list)
        message.save(self.user_events_path)
        return message.uuid


class Message:
    """Contains a single message as a JSON file."""
    def __init__(self, *, channel, target_id, message_type, **kwds):
        super().__init__(**kwds)
        self.channel = channel
        self.target_id = target_id
        self.message_type = message_type


class PersistableMessage(Message):
    """Abstract class that implements `save`. Subclasses must implement
    `file_stem`."""
    def save(self, events_path):
        """Create the message in a temp directory, and then move it into the
        corresponding inbox directory."""
        file_name = self.file_name()
        initial_path = Path(events_path, TEMP, file_name)
        final_path = Path(events_path, INBOX, file_name)
        with initial_path.open('w') as fout:
            dump(vars(self), fout, sort_keys=True)
        initial_path.rename(final_path)

    def file_name(self):
        """The file name to use when saving, including the extension."""
        return self.file_stem() + '.json'

    def file_stem(self):
        """The file name to use when saving, excluding the extension."""
        raise NotImplementedError


class NewRequestMessage(PersistableMessage):
    """A message from a user initiating a new Request. A request encapsulates:
    a UUID, a user name, a workflow, and a list of arguments. The UUID is
    computed upon initial construction and read from file when deserializing.
    The user name will be taken from the owner of the resulting JSON file when
    saved. Later a request gains an integer ID, which is provided by a
    single-threaded daemon process."""
    def __init__(self, workflow, arg_list, uuid_str=None, **kwds):
        super().__init__(
            channel=REQUEST,
            target_id=None,
            message_type=NEW,
            **kwds
        )
        self.uuid_str = uuid_str or str(uuid4())
        self.workflow = workflow
        self.arg_list = arg_list

    def file_stem(self):
        """Inherited from Message, uses the UUID."""
        return self.uuid_str

    @classmethod
    def from_file(cls, file_path):
        """Alternate constructor, loading from file. Gains user_name from
        the owner of the file."""
        file_path = Path(file_path)
        with file_path.open() as fin:
            mapping = load(fin)
        workflow = mapping['workflow']
        arg_list = mapping['arg_list']
        uuid_str = mapping['uuid_str']
        result = cls(workflow, arg_list, uuid_str)
        assert vars(result) == mapping, (vars(result), mapping)
        # TODO: fetch file uid or owner name and store
        return result
