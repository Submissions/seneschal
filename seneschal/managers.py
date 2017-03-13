"""Implements the managers, which are objects in between the engine and the
workers. There are four domains: user requests, batch jobs, local
subprocesses, and plugins. Everything begins with a user request, but almost
all actual work is defined by a plugin and then executed as either a batch
job or a subprocess."""

from pathlib import Path

from messaging import NEW, STARTED, SUCCEEDED, FAILED


logger = logging.getLogger(__name__)


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
        for subdir in self.directory.iterdir():
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
            worker = self.make_new_worker(worker_params)
            self.registry[worker.id] = worker
        else:
            worker = self.registry[message.target_id]
            worker.receive_message(worker_params)


class RequestManager(MessageReceiver):
    """The Manager for all Request objects."""
    def load(self):
        """Required by `OnFileSystemManager`."""
        pass  # TODO

    def receive_message(self, message):
        """Either create a new `Request` or pass the message to an existing
        `Request`."""
        pass  # TODO


# TODO: Synchonize documentation in messaging.py and tech_specs.md.
