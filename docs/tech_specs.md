# Seneschal Technical Specifications

Seneschal is an automation system that serves as a restricted control interface between users and a protected environment.

Features:

* accepts requests from users
* executes approved workflows
* will reject requests that violate policy
* creates an audit trail containing:
    * requests — who, what, when, input, output
    * request rejections
    * action start
    * action complete
    * errors
* is hardened — no database required
* is expandable — Users can write plugins, that define new workflows.
* is change managed — Administrators must install new plugins or versions, allowing change review and auditing.

## Main Concepts

Regular users issue commands that send _request_ _messages_. A _message_ is a small JSON file that specifies the desired action. For _requests_, the files are written to a special publicly writeable directory, the _inbox directory_.

A standard daemon named _seneschald_ polls the _inbox directory_, applies business and security rules, and then takes appropriate action such as rejecting the request, initiating a direct copy operation in a subprocess, or submitting a job to a batch scheduler. As is typical, the daemon has a PID file and responds to `SIGTERM` by shutting down after a few seconds.

With the exception of subprocesses executing copies, all state is maintained on the filesystem. This allows the daemon to recover from restart. Of course any subprocesses running local copies would be killed with the daemon, and those local copies would have to be restarted. This is not a problem if the copy is similar to rsync.

In addition to the normal logging expected of a daemon, the _seneschald_ daemon writes to a special _audit log_, noting all events that might be security relevant. These events are formatted to optimize ingestion by log analysis systems, such as splunk.

Batch jobs run inside a _job wrapper_ that sends start and finish _job events_ as _messages_ back to the daemon by writing small text files to a special directory that is different from the one used by users making requests. These messages usually trigger audit logging and progress updates to the _request_.

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
    drwxrwxr-x  seneschal  seneschal    ./seneschal/internal_events
    drwxrwxr-x  seneschal  seneschal    ./seneschal/job_events
    drwxrwxr-x  seneschal  seneschal    ./seneschal/job_events/0_temp
    drwxrwxr-x  seneschal  seneschal    ./seneschal/job_events/1_inbox
    drwxrwxr-x  seneschal  seneschal    ./seneschal/jobs
    drwxrwxr-x  seneschal  seneschal    ./seneschal/outbox
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/by_num
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/by_uuid
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/error
    drwxrwxr-x  seneschal  seneschal    ./seneschal/requests/finished
    drwxrwxr-x  seneschal  seneschal    ./seneschal/user_events
    drwxrwsrwt  seneschal  seneschal    ./seneschal/user_events/0_temp
    drwxrwsrwt  seneschal  seneschal    ./seneschal/user_events/1_inbox

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

It must be readable and writeable by the service account on the daemon host. It should be readable by developers on login nodes.

#### job events directory

The job events directory is where the batch job wrapper script will write events. It must be readable and writeable by the service account from both the daemon host and the cluster nodes used by seneschal.

It should be readable by developers on login nodes.

#### internal events directory

The internal events directory is for routing information between components of the system. Unlike job events and requests, these events do not come from the outside of the daemon. It must be readable and writeable by the service account. It should be readable by developers on login nodes.

#### outbox directory

The outbox directory is where seneschal places public messages intended to be read by user clients. It must:

* be writeable by the daemon
* be readable by both login and cluster nodes

It should be readable by developers on login nodes.

### plugins directory

Without plugins, the daemon does nothing ... very well. In this mode, all requests are errors. Plugins define whitelisted implementations of workflows.

The plugins directory only has to be readable by the daemon user on the daemon host.

Plugins have change management life-cycles independent of each other or the daemon. The goal is to enable each plugin to be auditable largely independently of the rest of the system. The directory for a plugin contains both name and version. Although this allows for limited backwards compatibility by have more than one active version, this capability should be used __very sparingly__.

Installing a plugin consists of unpacking it into the plugins directory. A plugin is a directory of files, minimally containing a module or executable with a standard name. If the plugin requires configuration, the configuration is stored in the configuration file under `plugins/the_plugin_name_and_version`.

For initial testing purposes, the core seneschal software will ship with a truly minimal set of plugins that are not quite as useful as `echo` and `ping`.

The plugins directory must be publicly readable on the _daemon host_ and all login nodes.

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
    * any optional or required configuration settings for the active plugins
* Write a systemd unit file that
    * knows the location of the PID file
    * defines a start command contaning:
        * Your Python 3.6
        * Your location for `seneschald.py`
        * Your config file
        * "start"
* Configure and deploy the `seneschal` script so that users can easily execute it.
* Test the `seneschal` script. (It can run without the daemon, and any messages it generates will be detected by the daemon when it runs.)
* Start the daemon like any other. (You could manually invoke `seneschald.py` with "start", but ... why?)
* Stop the daemon by like any other. The manual method is either sending a `SIGTERM` or invoking `seneschald.py` with "stop", which just does the same thing.
* When planning ahead for a stop, invoking `seneschald.py` with "drain" will notify to the daemon (by writing a special file) that it should postpone long-running local subprocesses, such as copies, until after "start" or "resume". The "drain" and "resume" events are idempotent.

Note that if seneschald is submitting a job to a batch scheduler or calling a webservice when `SIGTERM` is sent, then seneschald will not shutdown until after the batch scheduler acknowledges the job (e.g. bsub/msub/qsub exits) or the webservice returns.

__Question:__ Should the daemon remain in a drained state after restart? Should this be a configuration option?

## User Operation

User's interact with the seneschal system through porcelain commands. These commands do nothing more than scan directories, read files, and for _submit_ write files.

To list plugins:

    seneschal -l
    # A fancy ls of the plugins directory

To get documentation about a plugin:

    seneschal help PLUGIN_NAME
    # Runs the plugin's documentation (if any) through a pager
    # If there is no documentation file and the plugin supports it, instead
    # executes:
    #   ${PLUGINS_DIR}/${PLUGIN_NAME}/execute_job -h | ${PAGER}

To run a command:

    seneschal submit PLUGIN_NAME ARG1 ARG2 ...
    # Outputs the unique ID of the request

To check the status of a request:

    seneschal status UNIQUE_ID
    # Queries the seneschald files and generates a report

## Writing Plugins

TBD

## Developer Needs

In order to support and maintain the software, developers need to see recent logs and the contents of all of those directories.

Updates to either the daemon or a plugin consist of developers delivering checksummed tarballs for review and deployment.

## Implementation Design

The daemon code is written in Python. Messages are JSON files. Plugins can be written in any language that supports reading environment variables, command line argument parsing, and file I/O.

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
        debug_handler:
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
        handlers: [debug_handler]

The level of audit messages is always INFO or higher.

References:

* [http://dev.splunk.com/view/dev-guide/SP-CAAAE3A](http://dev.splunk.com/view/dev-guide/SP-CAAAE3A)
* [https://answers.splunk.com/answers/1951/what-is-the-best-custom-log-event-format-for-splunk-to-eat.html#answer-1953](https://answers.splunk.com/answers/1951/what-is-the-best-custom-log-event-format-for-splunk-to-eat.html#answer-1953)


### Architecture

These are the important kinds of objects in the system:

* daemon
* _Engine_
* managers
    * fertile
        * _RequestManager_
        * _JobManager_
        * _SubprocessManager_
    * sterile
        * _PluginManager_
* workers
    * stateful
        * _Request_
        * _Job_
        * _Subprocess_
    * stateless
        * _Plugin_
* _MessageBroker_
* _Message_
* _Event_

The _daemon_ reads the configuration file, constructs the _Engine_, and then start its main loop. During this loop, the _daemon_ passes control to the _Engine_. If there was no work for the _Engine_ to do, then the _daemon_ will sleep. The main loop terminates after `SIGTERM`.

The _Engine_ constructs instances of the _MessageBroker_ each type of manager. The engine will then go into a loop until the _daemon_ receives `SIGTERM`. Each pass through the loop will call upon the _MessageBroker_ to process one message. If there are no messages, then the _Engine_ returns control back to the _daemon_.

The _MessageBroker_ reads a _Message_ and converts it into an _Event_ for some worker or manager. A _Message_ and an _Event_ are similar, with the main difference being perspective. An object sends a _Message_ with a destination. That destination object receives an _Event_ where the destination is implicit and other contextual information may be added. Both messages and events are really just JSON files. (There's a lot of disk churn going on.)

Manager objects are responsible for creating and fetching workers. Managers maintain two kinds of state in memory:

* configuration
* a registry of workers, indexed by ID

When _seneschald_ starts up, each manager will reload its registry by scanning a directory.

Stateful workers uses the filesystem to maintain its state. Each stateful worker has a corresponding directory that contains an ordered list of JSON files corresponding to events, starting with an initialization event. The state of the worker is loaded into memory by reading each file in sequence.

Plugins have no state besides the configuration read from the main configuration file. Each time a plugin is invoked, it must be passed all the information it needs to do its job. It is the responsibility of stateful worker objects to hold the necessary state information. Some plugins are special, in that they define how the seneschal system integrates with external system like a compute cluster or permissions system. These plugins are typically aliased to logical resource names, like "batch\_scheduler". Most plugins are workflow plugins.

Plugins can be implemented as either external executables (usually scripts) or Python modules. There is no semantic difference between the two methods.

In the case of external executables, plugin configuration is defined in environment variables, and the input for the plugin is JSON data fed into standard input. The output is JSON data fed to standard output.

In the case of Python modules, a plugin is loaded by importing the module and then passing any configuration in the form of a Python _dict_ into a function in that module named _create_. The return value of that function call is the plugin object, which is callable. The input and output are just Python dictionaries. For some applications, Python modules are the better choice either because of better efficiency or simplicity.

Worker objects can do these things:

* __[not plugins]__ notify their manager that they should be purged
* __[not subprocesses]__ receive events
* send messages
* __[plugins and subprocesses only]__ do stuff

A _Request_ object represents — perhaps indirectly — a user's request to execute an automated workflow with a particular set of inputs and outputs. The owner of the request is the owner of the _Message_ file that originated the _Request_. Every _Request_ has an associated _workflow plugin_ that defines the actual workflow. After initialization, the _Request_ invokes the _workflow plugin_ passing in a JSON object representing the request. The plugin will respond with a _workflow_ — a JSON object containing a list of tasks that will satisfy the _Request_. The _Request_, will then typically trigger other messages, write its state to the filesystem, and exit. (The _Request_ could invoke other plugins as it iterates through the list of tasks.) Eventually the _Request_ will receive messages indicating the end of its various tasks. When there are no more tasks running, the _Request_ will have reached the end of its lifecycle. At that point, the _Request_ will notify the _RequestManager_ that it should be purged. Hopefully along the way, something useful happened.

A _Job_ represents a batch job submitted to a [job scheduler](https://en.wikipedia.org/wiki/Job_scheduler). A _Job_ is created when the _JobManager_ receives a _Message_ submitting a new _Job_. A _Job_ knows the ID of the originating _Request_. A _Job_ sends a message to the logical "batch\_scheduler" _Plugin_ to submit the job. The _Plugin_ will typically create a custom file for the job and then submit a plugin-defined wrapper script and that custom file to the underlying job scheduler. The wrapper script will then read the job-specific file, execute the required tasks, and send messages back to the _Job_ object upon the start and finish of compute. The _Job_ object will forward information back to the _Request_. The _Job_ object will notify the _JobManager_ when its lifecycle is complete.

A _Subprocess_ is a logical wrapper around an external command. It is much simpler than a _Job_, since there is not need for a plugin to implement it. The implementation is handled by the Python [subprocess module](https://docs.python.org/3/library/subprocess.html). State is also maintained on the filesystem. If the daemon must shutdown, all running subprocesses must be killed. By default, all subprocesses will restart when the daemon restarts. Workflows that use subprocesses are usually file copy operations. They should be coded so as to be restartable.

#### Example Putting it all Together

Consider a workflow that computes the MD5 checksum of a file. For the purpose of this discussion, let us agree to the interpretation that the MD5 of a protected file does not constitute protected information. Therefore, no security checks are required. A plugin implementing this workflow has two inputs: the input file path and the output file path.

This would be the sequence of received messages:

1.  _RequestManager_: new md5 inputPath outputPath
2.  request001: initialization userName md5 inputPath outputPath
3.  _JobManager_: new request001 step0 /usr/bin/md5sum inputPath outputPath
4.  job001: initialization request001 step0 /usr/bin/md5sum inputPath outputPath
5.  request001: step0 job submitted with ID 123
6.  job001 (sent by wrapper): compute started on node ABC at someTimestamp
7.  request001: step0 compute started on node ABC at someTimestamp
8.  job001 (sent by wrapper): compute succeeded at someTimestamp
9.  request001: step0 compute succeeded at someTimestamp
10. _JobManager_: purge job001
11. _RequestManager_: purge request001

This list does not show plugin invocations, since they are invoked by direct input — either function call or passing JSON into _stdin_.

Items 3, 10, and 11 are in-memory messages only, really just direct method calls. Even with optimization of those instantaneous messages staying in memory, there are at least 8 files created for this simplest cluster workflow.
