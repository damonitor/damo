# SPDX-License-Identifier: GPL-2.0

"""
Provides manual for given topics.
"""

import _damo_subcmds
import damo_help_access_filter_options
import damo_help_access_format_options
import damo_help_damon_param_options

subcmds = [
        _damo_subcmds.DamoSubCmd(
            name='damon_param_options', module=damo_help_damon_param_options,
            msg='DAMON parameter command line options'),
        _damo_subcmds.DamoSubCmd(
            name='access_filter_options',
            module=damo_help_access_filter_options,
            msg="DAMON monitoring results filtering options"),
        _damo_subcmds.DamoSubCmd(
            name='access_format_options',
            module=damo_help_access_format_options,
            msg="DAMON monitoring results visualization options"),
        ]

def main(args):
    for subcmd in subcmds:
        if subcmd.name == args.topic:
            subcmd.execute(args)

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='topic', dest='topic', metavar='<topic>',
            help='topic to get help for')
    subparsers.required = True

    for subcmd in subcmds:
        subcmd.add_parser(subparsers)
