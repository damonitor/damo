# SPDX-License-Identifier: GPL-2.0

import argparse

import _damon_args

def main(args):
    category = args.category
    parser = argparse.ArgumentParser(add_help=False)
    if category == 'monitoring':
        print('command line options for monitoring-part DAMON parameters')
        print()
        _damon_args.set_monitoring_argparser(parser, hide_help=False)
    elif category == 'damos':
        print('command line options for DAMOS parameters')
        print()
        _damon_args.set_damos_argparser(parser, hide_help=False)
    elif category == 'all':
        print('command line options for all DAMON parameters')
        print()
        _damon_args.set_misc_damon_params_argparser(parser)
    help_msg = parser.format_help()
    pars = help_msg.split('\n\n')
    # the first paragraph is usage for this virtual command.  Ignore.
    pars = pars[1:]
    if len(pars) == 1:
        print('\n'.join(pars[0].split('\n')[1:]))
    else:
        print('\n\n'.join(pars))
    if category == 'all':
        print(' '.join([
            "Also there are command line options for setting only monitoring",
            "and DAMOS-part DAMON parameters.",
            "Use 'damo help damon_param_options {monitoring,damos}'",
            "for those.",
            ]))

def set_argparser(parser):
    parser.add_argument(
            'category', choices=['all', 'monitoring', 'damos'],
            help='category of DAMON parameters to get help for')
    parser.description = 'help for DAMON parameters command line options'
    return parser
