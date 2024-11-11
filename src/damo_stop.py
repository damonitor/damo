# SPDX-License-Identifier: GPL-2.0

"""
Stop DAMON.
"""

import _damon
import _damon_args

def main(args):
    _damon.ensure_root_and_initialized(args, is_stop=True)

    running_kdamond_idxs = _damon.running_kdamond_idxs()
    if len(running_kdamond_idxs) == 0:
        print('DAMON is not turned on')
        exit(1)

    err = _damon.turn_damon_off(running_kdamond_idxs)
    if err:
        print('DAMON turn off failed (%s)' % err)
        exit(1)

def set_argparser(parser):
    _damon_args.set_common_argparser(parser)
    parser.description = 'Stop DAMON'
    return parser
