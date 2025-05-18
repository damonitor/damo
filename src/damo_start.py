# SPDX-License-Identifier: GPL-2.0

"""
Start DAMON with given parameters.
"""

import os

import _damon
import _damon_args

def main(args):
    _damon.ensure_root_and_initialized(args)

    for module in os.listdir('/sys/module'):
        if not module.startswith('damon_'):
            continue
        parm = os.path.join('/sys/module', module, 'parameters', 'enabled')
        running = False
        if os.path.isfile(parm):
            with open(parm, 'r') as f:
                running = f.read().strip()
        else:
            parm = os.path.join('/sys/module', module, 'parameters', 'enable')
            if os.path.isfile(parm):
                with open(parm, 'r') as f:
                    running = f.read().strip()
        if running == 'Y':
            print('Cannot turn on damon since %s is running.  '
                  'Disable it first.' % module)
            exit(1)

    err, kdamonds = _damon_args.turn_damon_on(args)
    if err:
        print('could not turn on damon (%s)' % err)
        exit(1)

def set_argparser(parser):
    _damon_args.set_argparser(parser, add_record_options=False, min_help=True)
    parser.description = 'Start DAMON with specified parameters'
    return parser
