# SPDX-License-Identifier: GPL-2.0

"""
Start DAMON with given parameters.
"""

import os
import signal
import time

import _damo_records
import _damon
import _damon_args

def sighandler(signum, frame):
    print('\nsingal %s received' % signum)
    exit(0)

def main(args):
    _damon.ensure_root_and_initialized(args)

    for module in os.listdir('/sys/module'):
        if not module.startswith('damon_'):
            continue
        param = os.path.join('/sys/module', module, 'parameters', 'enabled')
        running = False
        if os.path.isfile(param):
            with open(param, 'r') as f:
                running = f.read().strip()
        else:
            param = os.path.join('/sys/module', module, 'parameters', 'enable')
            if os.path.isfile(param):
                with open(param, 'r') as f:
                    running = f.read().strip()
        if running == 'Y':
            print('Cannot turn on damon since %s is running.  '
                  'Disable it first.' % module)
            exit(1)

    err, kdamonds = _damon_args.turn_damon_on(args)
    if err:
        print('could not turn on damon (%s)' % err)
        exit(1)

    if args.include_child_tasks is True:
        signal.signal(signal.SIGINT, sighandler)
        signal.signal(signal.SIGTERM, sighandler)
        print('Continue monitoring child tasks and updating DAMON targets')
        print('Press Ctrl+C to stop')
        while True:
            _damo_records.add_childs_target(kdamonds)
            time.sleep(3)

def set_argparser(parser):
    _damon_args.set_argparser(parser, add_record_options=False, min_help=True)
    parser.add_argument('--include_child_tasks', action='store_true',
                        help='add child tasks as monitoring target')
    parser.description = 'Start DAMON with specified parameters'
    return parser
