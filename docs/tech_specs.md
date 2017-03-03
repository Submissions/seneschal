# Seneschal Technical Specifications

Seneschal is an automation system that serves as a restricted control interface between users and a protected environment.

__TODO:__ Add it Keith's ideas about:
* auto-discovery
* language-agnostic plugins.
* user-facing porcelain commands

## Main Concepts

Regular users issue commands that send _request_ _messages_. A _message_ is a small JSON file that specifies the desired action. For _requests_, the files are written to a special publicly writeable directory, the _inbox directory_.

A standard daemon named _seneschald_ polls the _inbox directory_, applies business and security rules, and then takes appropriate action such as rejecting the request, initiating a direct copy operation in a subprocess, or submitting a job to a cluster. As is typical, the daemon has a PID file and responds to `SIGTERM` by shutting down after a few seconds.

With the exception of subprocesses executing copies, all state is maintained on the filesystem. This allows the daemon to recover from restart. Of course any subprocesses running local copies would be killed with the daemon, and those local copies would have to be restarted. This is not a problem if the copy is similar to rsync.

In addition to the normal logging expected of a daemon, the _seneschald_ daemon writes to a special _audit log_, noting all events that might be security relevant. These events are formatted to optimize ingestion by log analysis systems, such as splunk.

Cluster jobs run inside a _job wrapper_ that sends start and finish _job events_ as _messages_ back to the daemon by writing small text files to a special directory that is different from the one used by users making requests. These messages usually trigger audit logging and progress updates to the _request_.

The _seneschald_ daemon is just a framework for automation. Almost all of the security logic and workflow machinery is provided by _plugins_. This allows more efficient change management, since the plugins will evolve on different timescales from each other and the daemon.

Borrowing from git documentation, we use the analogy of plumbing and porcelain. Plumbing is the machinery required for the system to operate: daemon, plugins, etc. Porcelain is the set of user-facing commands that make the system useful: making requests, checking status, etc. Without the porcelain, the plumbing is pointless.

* message
* request
* inbox directory
* seneschald
* audit log
* job wrapper
* job events
* plugins
* porcelain

## Deployment Requirements

* service account
* daemon host
* daemon directories
* plugins directory
* cluster resources
* software directory

### service account

* The daemon must run with the UID set to a non-root, non-login service account.

* In order to facilitate fulfilling user requests for data this service account will belong to multiple regular user groups. Otherwise the users would have to create publicly writeable directories to receive the output that they are requesting.

* Recommendations:
    * The name of the service account should include "seneschal".
    * There should be an associated group with the same name.

### daemon host

The host running the daemon must:

* mount all relevant filesystems
    * These filesystems may be mounted read-only:
        * protected upstream filesystems
        * software filesystems
    * These must be mounted read-write:
        * destination filesystems
            * user filesystems
            * data transfer filesystems
        * filesystems holding:
            * inbox directory
            * processing directory
            * job events directory
            * logging
* have enough capacity in cores and bandwidth to support daily data transfer operations
* share the same service account name and numeric ID as the compute cluster

### daemon directories

In order to process requests and track state, the daemon needs an assortment of directories. Two of these directories must be publicly writeable. It is easiest if they are all publicly readable.

This is the recommended structure:

    drwxrwxr-x  seneschal  seneschal    ./seneschal
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests
    drwxrwsrwt  seneschal  seneschal    ./seneschal/requests/0_temp
    drwxrwsrwt  seneschal  seneschal    ./seneschal/requests/1_inbox
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/2_processing
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/3_error
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/3_finished
    drwxrwxr-x  seneschal  seneschal    ./seneschal/job_events

The idea is for the daemon to track state through a clean system reboot (`SIGTERM` + timeout), even restarting interrupted copies that were running locally.

#### temp and inbox directories

The inbox directory should be visible to all user login nodes and user compute nodes. They must:

* be on the same filesystem
* have permissions `drwxrwsrwt`
* be accessible to users (All parent directories are `o+rx`.)
* be owned by _seneschald_ service account
* be in a group that contains the service account and does not include users
* be on the same filesystem as the processing directory

#### processing directory

The processing directory is where _seneschald_ maintains most of its state. It contains a moderate number of small files, separated by request into subdirectories. It must:

* be on the same filesystem as the inbox directory
* be owned by _seneschald_ service account
* be in the same group as the inbox directory

It should:

* be readable by developers on login nodes
* be readable by regular users on login nodes so that they can receive status reports (Obscurity is not our friend.)

#### error and finished directories

Where _requests_ go at the end. There will be some sort of consolidation (such as tar) and cleanup (such as archiving). TBD

#### job events directory

The job events directory is where the cluster job wrapper script will write events. It must:

* be accessible to the cluster nodes used by seneschal
* be readable and writeable by the service account

### plugins directory

Without plugins, the daemon does nothing ... very well. In this mode, all requests are errors. Plugins define whitelisted implementations of workflows.

The plugins directory only has to be readable by the daemon user on the daemon host.

Plugins have change management life-cycles independent of each other or the daemon. The goal is to enable each plugin to be auditable largely independently of the rest of the system.

Installing a plugin consists of unpacking it into the plugins directory. A plugin is a directory of files, minimally containing a script file with a standard name.

### cluster resources

The mounting requirements for compute nodes serving seneschal are a subset of those on the daemon host:

* These filesystems may be mounted read-only:
    * upstream filesystems
    * software filesystems
* These must be mounted read-write:
    * user filesystems
    * the filesystem holding the job events directory

### software directory

In addition to other standard software directories, the seneschal software must be available to all users, the daemon host, and the compute nodes. In particular:

* Users must have access to the scripts that generate _requests_.
* Compute jobs must have access to the seneschal wrapper.
* The daemon must have access to its own machinery and all the plugins.

Easiest is to just make everything public.

## Deployment and Operating Instructions

__NOTE:__ Except for temp and inbox, none of these directories or files should be writable by users.

* Install Python 3.6 somewhere accessible to the daemon host.
* Unpack the seneschal tarball, which contains its third-party dependencies.
* Create the necessary directories.
* Copy all the active plugins into some directory, such as a directory named "plugins" just inside the unpacked tarball.
* Write a config file, which specifies:
    * PID file
    * logging destinations
    * daemon process settings
    * directory locations
    * active plugins and their settings
* Write a systemd unit file that
    * knows the location of the PID file
    * defines a start command contaning:
        * Your Python 3.6
        * Your location for `seneschald.py`
        * Your config file
        * "start"
* Start the daemon like any other. (You could manually invoke `seneschald.py` with "start", but ... why?)
* Stop the daemon by like any other. The manual method is either sending a `SIGTERM` or invoking `seneschald.py` with "stop", which just does the same thing.
* When planning ahead for a stop, invoking `seneschald.py` with "drain" will notify to the daemon (by writing a special file) that it should postpone long-running local subprocesses, such as copies, until after "start" or "resume". The "drain" and "resume" events are idempotent.

Note that if seneschald is submitting a job to a cluster or calling a webservice when `SIGTERM` is sent, then seneschald will not shutdown until after the cluster acknowledges the job (e.g. qsub exits) or the webservice returns.

__Question:__ Should the daemon remain in a drained state after restart? Should this be a configuration option?

## Developer Needs

In order to support and maintain the software, developers need to see recent logs and the contents of all of those directories.

Updates consist of the developers delivering Python source code for review and deployment.

## Implementation Design

Most of the code is written in Python.

The daemon uses two third-party packages:

* [python-daemon](https://pypi.python.org/pypi/python-daemon): implements [PEP 3143](https://www.python.org/dev/peps/pep-3143/)
* [lockfile](https://pypi.python.org/pypi/lockfile): provides PID file support, may switch to [pid](https://pypi.python.org/pypi/pid)

### Logging & Auditing

Logging and auditing is handled through the Python standard library [logging module](https://docs.python.org/3/library/logging.html). Logging is configured using [logging.config.dictConfig](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig). The necessary dictionary is read from the config file under the "logging" section with these two keys added by `seneschald`:

    version=1
    disable_existing_loggers=False

Much of the internal logging is handled in a manner that is typical for well behaved, long-running Python processes. Logging messages intended for developers or system administrators are human-friendly. The audit log is special.

There is a special logger named "audit". Log messages sent to this logger will be optimized for ingestion by log analysis systems, such as splunk:

    timestamp key1=value1 key2=value2 key3=value3 key4=value4 ...

Example of the section of the config file that configures logging:

    logging:
      formatters:
        verbose:
          format: '%(asctime)s %(levelname)-8s %(name)s %(module)s %(process)d %(message)s'
        audit_format:
          format: '%(asctime)s %(message)s'
      handlers:
        debug:
          class : logging.handlers.RotatingFileHandler
          formatter: verbose
          filename: /var/log/seneschal/debug.log
          maxBytes: 40960
          backupCount: 1
        audit_handler:
          class : logging.handlers.RotatingFileHandler
          formatter: audit_format
          filename: /var/log/seneschal/audit.log
          maxBytes: 409600
          backupCount: 4
      loggers:
        audit:
          level: INFO
          handlers: [audit_handler]
      root:
        level: DEBUG
        handlers: [debug]

The level of audit messages is always INFO or higher.

References:

* [http://dev.splunk.com/view/dev-guide/SP-CAAAE3A](http://dev.splunk.com/view/dev-guide/SP-CAAAE3A)
* [https://answers.splunk.com/answers/1951/what-is-the-best-custom-log-event-format-for-splunk-to-eat.html#answer-1953](https://answers.splunk.com/answers/1951/what-is-the-best-custom-log-event-format-for-splunk-to-eat.html#answer-1953)


### Objects, Events, and Messages

Stay tuned.
