# Seneschal Technical Specifications

Seneschal is an automation system that serves as a restricted control interface between users and a protected environment.

## Main Concepts

Regular users issue commands that create `requests` in a specially publicly writeable directory, the inbox directory. A `request` is asmall JSON files that specify the desired action.

A standard daemon named `seneschald` polls this directory, applies business and security rules, and then takes appropriate action such as rejecting the request, initiating a direct copy operation in a subprocess, or submitting a job to a cluster. The daemon has a PID file and responds to SIGTERM by shutting down after one or two seconds.

In addition to the normal logging expected of a daemon, the `seneschal` daemon writes to a special audit log, noting all events that might be security relevant.

Cluster jobs run inside a wrapper script that sends start and finish events back to the daemon by writing small text files to a special directory that is different from the one used by users making requests.

The `seneschald` daemon is just a framework for automation. Almost all of the security logic and workflow machinery is provided by plugins. This allows more efficient change management, since the plugins will evolve on different timescales from each other and the daemon.

* request
* inbox directory
* seneschald
* job wrapper
* audit log
* job events

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
        * production filesystems
        * software filesystems
    * These must be mounted read-write:
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

The idea is for the daemon to track state through a clean system reboot (SIGTERM + 2 second timeout), even restarting interrupted copies that were running locally.

#### temp and inbox directories

The inbox directory should be visible to all user login nodes and user compute nodes. They must:

* be on the same filesystem
* have permissions `drwxrwsrwt`
* be accessible to users (All parent directories are `o+rx`.)
* be owned by `seneschald` service account
* be in a group that contains the service account and does not include users
* be on the same filesystem as the processing directory

#### processing directory

The processing directory is where `seneschald` maintains most of its state. It contains a moderate number of small files, separated by request into subdirectories. It must:

* be on the same filesystem as the inbox directory
* be owned by `seneschald` service account
* be in the same group as the inbox directory

It should:

* be readable by developers on login nodes
* be readable by regular users on login nodes so that they can receive status reports (Obscurity is not our friend.)

#### error and finished directories

Where requests go at the end. There will be some sort of consolidation (such as tar) and cleanup (such as archiving). TBD

#### job events directory

The job events directory is where the cluster job wrapper script will write events. It must:

* be accessible to the cluster nodes used by seneschal
* be readable and writeable by the service account

### plugins directory

Without plugins, the daemon does nothing ... very well. In this mode, all requests are errors. Plugins define whitelisted implementations of workflows.

The plugins directory only has to be readable by the daemon user on the daemon host.

Plugins have change management life-cycles independent of each other or the daemon. The goal is to enable each plugin to be auditable largely independently of the rest of the system.

Installing a plugin consists of unpacking it into the plugins directory. A plugin is a directory of files, minimally containing a .py file with the same name as the parent directory.

### cluster resources

The mounting requirements for compute nodes serving seneschal are a subset of those on the daemon host:

* These filesystems may be mounted read-only:
    * production filesystems
    * software filesystems
* These must be mounted read-write:
    * user filesystems
    * the filesystem holding the job events directory

### software directory

In addition to other standard software directories, the seneschal software must be available to all users, the daemon host, and the compute nodes. In particular:

* Users must have access to the scripts that generate `requests`.
* Compute jobs must have access to the seneschal wrapper.
* The daemon must have access to its own machinery and all the plugins.

Easiest is to just make everything public.

## Deployment and Operating Instructions

**NOTE:** Except for temp and inbox, none of these directories or files should be writable by users.

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
* Stop the daemon by like any other. The manual method is either sending a SIGTERM or invoking `seneschald.py` with "stop", which just does the same thing.
* When planning ahead for a stop, invoking `seneschald.py` with "drain" will notify to the daemon (by writing a special file) that it should postpone long-running local subprocesses, such as copies, until after "start" or "resume". The "drain" and "resume" events are idempotent.

**Question:** Should the daemon remain in a drained state after restart? Should this be a configuration option?

## Developer Needs

In order to support and maintain the software, developers need to see recent logs and the contents of all of those directories.

Updates consist of the developers delivering Python source code for review and deployment.

## Implementation Design

Stay tuned.

### Logging & Auditing

Stay tuned.

1. Item 1

1. Item 2

    1. Item 2a
    1. Item 2b

1. Item 3
