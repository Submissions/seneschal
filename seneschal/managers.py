"""Implements the managers, which are objects in between the engine and the
workers. There are four domains: user requests, batch jobs, local
subprocesses, and plugins. Everything begins with a user request, but almost
all actual work is defined by a plugin and then executed as either a batch
job or a subprocess.

Stateful workers are persisted to the filesystem in paths like this:

    SOME_ROOT/by_uuid/12300000-0000-0000-0000-000000000000/0.json
    SOME_ROOT/by_uuid/12300000-0000-0000-0000-000000000000/1.json
    SOME_ROOT/by_uuid/12300000-0000-0000-0000-000000000000/2.json

In this example, SOME_ROOT is the directory associated with a manager, 123...
is the UUID or ID of the worker and 2.json is the most recent state for that
worker

"""

from json import dump, load
import logging
from pathlib import Path

from .messaging import NEW, STARTED, SUCCEEDED, FAILED


logger = logging.getLogger(__name__)

UUID_GLOB = '????????-????-????-????-????????????'
WORKER_GLOB = 'by_uuid/' + UUID_GLOB


class Manager:
    """Abstract base class that encapsulates the concept of workers, an
    associated filesystem directory containing worker-specific subdirectories,
    the ability to load workers from their subdirectories during startup,
    a registry of workers by ID, and the ability to send messages to a
    `messaging.MessageBroker`. Subclasses must implement `load`."""

    def __init__(self, *, directory, worker_class, **kwds):
        """Load state from directory into memory."""
        super().__init__(**kwds)
        self.directory = Path(directory)
        self.worker_class = worker_class
        self.message_broker = None  # See set_message_broker
        assert self.directory.is_dir()
        self.registry = dict()  # ID -> worker
        for subdir in self.directory.glob(WORKER_GLOB):
            worker_params = self.load(subdir)
            self.add_worker(worker_params)

    def set_message_broker(self, message_broker):
        """Called after construction to install the `messaging.MessageBroker`.
        Should only be called once."""
        assert self.message_broker is None
        self.message_broker = message_broker

    def load(self, subdir):
        """Abstract method to load worker state by reading the filesystem at
        `subdir`. Returns a `dict` of worker state."""
        raise NotImplementedError('abstract method')

    def add_worker(self, worker_params):
        """Construct a new worker, and install it in the `registry`.
        Return the new worker's ID."""
        worker = self.worker_class(worker_params)
        self.registry[worker.id] = worker
        return worker.id


class MessageReceiver(Manager):
    """Abstract base class for Manager that can receive external messages.
    Subclasses must implement `load`."""

    def receive_message(self, message):
        """Called by `messaging.MessageReceiver`, returns nothing. If
        `target_id` is None, then `message_type` should be `NEW`, in which
        case we should create a new worker object with the message payload.
        Otherwise, `target_id` should reference an existing object, and we
        should pass the message to that object by method call."""
        worker_params = dict(vars(message))
        # Remove parameters no longer needed.
        worker_params.pop(channel)
        worker_params.pop(message_type)
        worker_params.pop(target_id)
        if message.target_id is None:
            assert message.message_type is NEW
            worker = self.add_worker(worker_params)
        else:
            worker = self.registry[message.target_id]
            worker.receive_message(worker_params)
        worker.save()


class RequestManager(MessageReceiver):
    """The Manager for all Request objects."""

    def __init__(self, **kwds):
        """Load state from directory into memory."""
        super().__init__(**kwds, worker_class=Request)

    def load(self, subdir):
        """Required by `Manager`. Delegates to `load_most_recent_state`."""
        return load_most_recent_state(subdir)


class DictProxy:
    """A class that links its state to an existing dict; a flyweight facade
    wrapping a dict. Any changes to the object are changes to the dict."""
    def __init__(self, mapping):
        self.__dict__ = mapping

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.__dict__)


class Request(DictProxy):
    pass  # TODO


class Task(DictProxy):
    """Abstract base class for all tasks. Every `Task` obtains and maintains
    its state in an external dict."""
    # The static method `register_concrete_subclass` is a class decorator
    # that will populate concrete_subclasses, which enables `from_dict`.
    concrete_subclasses = {}

    def __init__(self, mapping):
        """Validates mapping and delegates construction to superclass."""
        assert 'type' in mapping
        super().__init__(mapping)

    @staticmethod
    def from_dict(mapping):
        """Return the appropriate type of `Task` object based on the contents
        of `mapping`."""
        assert isinstance(mapping, dict)
        subclass_selection = mapping['type']
        subclass = Task.concrete_subclasses[subclass_selection]
        return subclass(mapping)

    @staticmethod
    def register_concrete_subclass(cls):
        """A class decorator that registers concrete Task subclasses.
        Subclasses must implement a class member __task_type_id__ as the str
        that will be used during deserialization to select the appropriate
        subclass."""
        Task.concrete_subclasses[cls.__task_type_id__] = cls
        return cls

    def start(self, message_broker):
        """Abstract method. Invoked by the `Request` or a parent `CompoundTask`
        when it is time for this `Task` to start. Subclasses should either
        `start` a sub-task or send a `Message` by invoking
        `message_broker.deliver_one_message`."""
        raise NotImplementedError


@Task.register_concrete_subclass
class BatchJobTask(Task):
    """Executes asynchronously in a batch job."""
    __task_type_id__ = 'batch_job'
    pass  # TODO


@Task.register_concrete_subclass
class SubprocessTask(Task):
    """Executes asynchronously in a subprocess."""
    __task_type_id__ = 'subprocess'
    pass  # TODO


class CompoundTask(Task):
    """A `Task` that implements `children`, which must be a list of `Tasks`."""
    # We store the children under a key named "zchildren" for a serialized
    # state that is easier to read.

    def __getitem__(self, key):
        return self.children[key]

    @property
    def children(self):
        """Returns a list of the appropriate `Task` objects."""
        return [Task.from_dict(child) for child in self.zchildren]


@Task.register_concrete_subclass
class SequenceTask(CompoundTask):
    """Executes a list of child `Task`s in sequence."""
    __task_type_id__ = 'sequence'
    pass  # TODO


@Task.register_concrete_subclass
class ParallelTask(CompoundTask):
    """Executes a list of child `Task`s in parallel."""
    __task_type_id__ = 'parallel'
    pass  # TODO


def load_most_recent_state(state_files_dir):
    """Read the highest numbered state file as JSON and return the result."""
    assert isinstance(state_files_dir, Path), state_files_dir
    assert state_files_dir.match(UUID_GLOB), state_files_dir
    state_files = sorted(enumerate_numbered_json_files(state_files_dir))
    assert state_files, state_files_dir
    state_file = state_files[-1][1]
    with state_file.open() as fin:
        state = load(fin)
    return state


def enumerate_numbered_json_files(directory):
    """Yield pairs of num & json_file_path."""
    for json_file_path in directory.glob('*.json'):
        try:
            num = int(json_file_path.stem)
            yield num, json_file_path
        except Exception as e:
            pass  # TODO: log the unusual file


def propagate_inheritance(mapping, path='t'):
    """Given a mapping that represents the state of a possibly compound `Task`,
    bestows inheritable attributes to children that have not overridden
    those attributes. Each `Task` will have a path relative to the `Request`
    object. The root `Task` has a path of "t", the zeroth child has a path
    of "t/0", and the zeroth grandchild has a path of "t/0/0"."""
    mapping['path'] = path
    if 'zchildren' not in mapping:
        return  # Nothing to do
    child_type = mapping.get('child_type', None)
    keys = set(mapping)  # Will be the set of inheritable keys.
    # Children do not inherit these:
    keys.discard('zchildren')
    keys.discard('child_type')  # optional
    keys.remove('type')  # but they can get type from child_type
    # Give the children their inheritances:
    for index, child_mapping in enumerate(mapping['zchildren']):
        child_mapping['index'] = index
        if not 'type' in child_mapping:
            assert child_type is not None
            child_mapping['type'] = child_type
        for key in keys:
            if key not in child_mapping:
                child_mapping[key] = mapping[key]
        # Give the child object a chance to initialize state:
        propagate_inheritance(child_mapping, f'{path}/{index}')


def index_mappings(mapping):
    """Return a `dict` of all nested mappings, including the root, where the
    key is the value for "path". Uses `iterate_nested_mappings`, and requires
    that every mapping have a key of "path"."""
    result = {value['path']: value
              for value in iterate_nested_mappings(mapping)}
    return result


def iterate_nested_mappings(mapping):
    """Generator function that top-down iterates all the mapping objects.
    Children are expected to be in a iterable under the key `zchildren`. The
    iterator always yields something, since the first value is always
    the `mapping` parameter."""
    yield mapping
    for child_mapping in mapping.get('zchildren', ()):
        yield from iterate_nested_mappings(child_mapping)


# TODO: Synchonize documentation in messaging.py and tech_specs.md.
