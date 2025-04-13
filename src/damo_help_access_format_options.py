# SPDX-License-Identifier: GPL-2.0

import argparse

import damo_report_access

def main(args):
    if args.subtopic == 'record_format_keywords':
        print('\n\n'.join(
            ['%s' % f for f in damo_report_access.record_formatters]))
        return
    if args.subtopic == 'snapshot_format_keywords':
        print('\n\n'.join(
            ['%s' % f for f in damo_report_access.snapshot_formatters]))
        return
    if args.subtopic == 'region_format_keywords':
        print('\n\n'.join(
            ['%s' % f for f in damo_report_access.region_formatters]))
        return

    print('command line options for monitoring results visualization options')
    parser = argparse.ArgumentParser(add_help=False)
    damo_report_access.add_fmt_args(parser)
    help_msg = parser.format_help()
    pars = help_msg.split('\n\n')
    # the first paragraph is usage for this virtual command.  Ignore.
    pars = pars[1:]
    if len(pars) == 1:
        print('\n'.join(pars[0].split('\n')[1:]))
    else:
        print('\n\n'.join(pars))

def set_argparser(parser):
    parser.description = 'help for DAMON monitoring results visualization options'
    parser.add_argument(
            'subtopic', nargs='?',
            default='options',
            choices=['options', 'record_format_keywords',
                     'snapshot_format_keywords', 'region_format_keywords'],
            help='sub-topic to get help')
    return parser
