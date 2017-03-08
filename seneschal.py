"""User interface to the Seneschal automation system. Everything is a
subcommand."""


import argparse
import json
import sys

import yaml


emit = lambda *args: None  # Do nothing


def main():
    global emit
    args = parse_args()
    if args.verbose:
        emit = err_output
    config = load_config_file(args.config_file)
    seneschal_config = config['seneschal']
    try:
        args.func(seneschal_config, args)
    except BrokenPipeError as e:
        pass  # Ignore. Something like head is truncating output.
    finally:
        sys.stderr.close()  # Needed to supress meaningless BrokenPipeError.


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('config_file', help='path to YAML file')
    subparsers = parser.add_subparsers(help='sub-commands')

    # create the parser for the "submit" command
    parser_submit = subparsers.add_parser(
        'submit',
        help='Submit a request to the Seneschal automation system.'
    )
    parser_submit.add_argument('workflow', help='what to do')
    parser_submit.add_argument('args', nargs='*', help='workflow-specific')
    parser_submit.set_defaults(func=submit)

    # create the parser for the "ls" command
    parser_ls = subparsers.add_parser('ls', help='List workflows')
    parser_ls.set_defaults(func=ls)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.error('missing subcommand (subcommand, ls, etc.)')

    return args


def load_config_file(config_file):
    with open(config_file) as fin:
        config = yaml.load(fin)
    return config


def submit(seneschal_config, args):
    """Submit a request to the Seneschal automation system."""
    emit(args)
    emit('workflow:', args.workflow)
    for arg in args.args:
        emit(arg)
    yaml.safe_dump(seneschal_config, sys.stdout, default_flow_style=False)
    # try:
    #     for i in range(200000):
    #         print(i)
    # finally:
    #     emit('got to', i)
    pass  # TODO


def ls(seneschal_config, args):
    """List workflows."""
    print(args)
    yaml.safe_dump(seneschal_config, sys.stdout, default_flow_style=False)
    pass  # TODO


def err_output(*args):
    """Send args to sys.stderr."""
    print(*args, file=sys.stderr)


if __name__ == "__main__":
    main()
