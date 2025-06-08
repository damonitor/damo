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

def module_running(module_name):
    param_dir = os.path.join('/sys/module', module_name, 'parameters')
    for param_name in ['enabled', 'enable']:
        param_file = os.path.join(param_dir, param_name)
        if os.path.isfile(param_file):
            with open(param_file, 'r') as f:
                return f.read().strip() == 'Y'
    return False

def module_disable(module_name):
    param_dir = os.path.join('/sys/module', module_name, 'parameters')
    for param_name in ['enabled', 'enable']:
        param_file = os.path.join(param_dir, param_name)
        if os.path.isfile(param_file):
            with open(param_file, 'w') as f:
                f.write('N')
                return

def handle_modules():
    for module in os.listdir('/sys/module'):
        if not module.startswith('damon_'):
            continue
        if not module_running(module):
            continue
        print('Cannot turn on damon since %s is running.  '
              'You should disable it first.' % module)
        answer = input('May I disable it for you? [Y/n] ')
        if answer.lower() == 'n':
            print('Ok, see you later')
            exit(1)
        print('Ok, disabling it')
        module_disable(module)
        print('Disabled it.  Continue starting DAMON')

def sighandler(signum, frame):
    print('\nsingal %s received' % signum)
    exit(0)

def main(args):
    _damon.ensure_root_and_initialized(args)
    handle_modules()

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
