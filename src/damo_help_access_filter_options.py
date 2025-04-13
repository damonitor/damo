# SPDX-License-Identifier: GPL-2.0

import argparse

import _damo_records

def main(args):
    print('command line options for monitoring results visualization options')
    parser = argparse.ArgumentParser(add_help=False)
    _damo_records.set_filter_argparser(parser, hide_help=False)
    help_msg = parser.format_help()
    pars = help_msg.split('\n\n')
    # the first paragraph is usage for this virtual command.  Ignore.
    pars = pars[1:]
    if len(pars) == 1:
        print('\n'.join(pars[0].split('\n')[1:]))
    else:
        print('\n\n'.join(pars))

def set_argparser(parser):
    parser.description = 'help for DAMON monitoring results filtering options'
    return parser
