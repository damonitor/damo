# SPDX-License-Identifier: GPL-2.0

"Record and report data access pattern in realtime"

import os
import signal
import subprocess
import sys

import _damon
import _damon_args

def cleanup():
    if target_type == _damon_args.target_type_cmd and cmd_pipe.poll() == None:
        cmd_pipe.kill()
    damo = sys.argv[0]
    subprocess.call(
            [damo, 'stop'],
            # DAMON may already stopped, but that's fine.  Ignore error
            # message.
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def sighandler(signum, frame):
    print('\nsignal %s received' % signum)
    cleanup()

def main(args):
    _damon.ensure_root_permission()

    global target_type
    global cmd_pipe

    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    target = args.target
    target_type = _damon_args.deduced_target_type(target)
    if target_type == None:
        print('invalid target \'%s\'' % target)
        exit(1)
    if target_type == _damon_args.target_type_explicit and target == 'paddr':
        pass
    elif target_type == _damon_args.target_type_cmd:
        cmd_pipe = subprocess.Popen(target, shell=True, executable='/bin/bash',
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        target = cmd_pipe.pid
    else:
        pid = int(target)

    damo = sys.argv[0]

    if subprocess.call([damo, 'start', '%s' % target]) != 0:
        print('starting DAMON fail')
        exit(1)

    record_cmd = [damo, 'record', '--timeout', '%f' % args.delay, 'ongoing']

    report_cmd = [damo, 'report']
    if args.report_type == 'heats':
        report_cmd += ['heatmap', '--resol', '10', '80',
                       '--time_range', '%f s' % (args.delay * -1), '0 s',
                       'guided_end']
    else:
        report_cmd += [args.report_type]
        if args.report_type == 'holistic':
            report_cmd += ['--heatmap_time_last_n_sec', '%f' % args.delay]

    nr_reports = 0
    while not args.count or nr_reports < args.count:
        if (target_type == _damon_args.target_type_cmd and
                cmd_pipe.poll() != None):
            break
        try:
            subprocess.check_output(record_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print('Recording fail (%s)' % e)
        try:
            output = subprocess.check_output(report_cmd).decode()
            if args.report_type == 'heats':
                for line in output.strip().split('\n'):
                    if not line.startswith('#'):
                        print(line)
            else:
                print(output)
        except subprocess.CalledProcessError as e:
            print('Report generating fail (%s)' % e)
        nr_reports += 1

    cleanup()

def set_argparser(parser):
    parser.add_argument('target', type=str, metavar='<target>',
            help='monitoring target (command, pid or \'paddr\')')
    parser.add_argument(
            '--report_type', type=str, choices=['heats', 'wss', 'holistic'],
            default='heats', help='report type')
    parser.add_argument('--delay', type=float, metavar='<seconds>', default=3,
            help='deplay between updates in seconds.')
    parser.add_argument('--count', type=int, metavar='<count>', default=0,
            help='number of updates.')
