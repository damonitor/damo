# SPDX-License-Identifier: GPL-2.0

import signal
import subprocess

import _damo_subproc
import _damo_sysinfo
import _damon

tracer_pipe = None

def signalhandler(signum, frame):
    print('signal %s received' % signum)
    if tracer_pipe:
        try:
            tracer_pipe.send_signal(signum)
            tracer_pipe.wait()
        except:
            pass
    exit(0)

def main(args):
    global tracer_pipe

    _damon.ensure_root_permission()

    if args.event is None:
        print('--event is required')
        exit(1)

    if _damo_subproc.avail_cmd('perf'):
        cmd = ['perf', 'trace']
    elif _damo_subproc.avail_cmd('trace-cmd'):
        cmd = ['trace-cmd', 'stream']
    for trace_event in args.event:
        cmd.append('-e')
        cmd.append(trace_event)

    signal.signal(signal.SIGINT, signalhandler)
    signal.signal(signal.SIGTERM, signalhandler)

    tracer_pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    while True:
        output = tracer_pipe.stdout.readline()
        if not output and tracer_pipe.poll() is not None:
            break
        print(output.decode(), end='')

def set_argparser(parser):
    damon_tracepoints = list(
            _damo_sysinfo.tracepoint_to_feature_name_map.keys())
    parser.add_argument(
            '--event', choices=damon_tracepoints + ['all'], nargs='+',
            help='events to trace')
