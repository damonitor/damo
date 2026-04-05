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

damon_trace_events = _damo_sysinfo.tracepoint_to_feature_name_map.keys()

def report_recorded_trace(args):
    trace_text_format = None
    try:
        trace_text = subprocess.check_output(
                ['perf', 'script', '--force', '-i', args.input]).decode()
        trace_text_format = 'perf'
    except Exception as perf_e:
        try:
            trace_text = subprocess.check_output(
                    ['trace-cmd', 'report', '-i', args.input]).decode()
            trace_text_format = 'trace-cmd'
        except Exception as trace_cmd_e:
            print('cannot parse %s using neither perf (%s) nor trace-cmd (%s)'
                  % (args.input, perf_e, trace_cmd_e))
            return -1

    if args.event is None:
        print('--event is required')
        exit(1)

    events = []

    if 'all' in args.event:
        events = list(damon_trace_events)
    else:
        events = args.event
    if args.no_event is not None:
        for event in args.no_event:
            events.remove(event)

    for line in trace_text.split('\n'):
        fields = line.split()
        # perf script and trace-cmd report puts the event name on fifth field.
        # perf:
        #   kdamond.0  4452 [000] 82877.315633: damon:damon_aggregated: ...
        # trace-cmd:
        #   kdamond.0-264454 [007] ..... 92627.258073: damon_aggregated: ...
        if len(fields) < 5:
            continue
        event = fields[4][:-1]
        if not event in events:
            continue
        print(line)

def main(args):
    if args.input is not None:
        return report_recorded_trace(args)

    global tracer_pipe

    _damon.ensure_root_permission()

    if args.event is None:
        print('--event is required')
        exit(1)

    events = []

    if 'all' in args.event:
        events = list(damon_trace_events)
    else:
        events = args.event
    if args.no_event is not None:
        for event in args.no_event:
            events.remove(event)

    if args.tracer is None:
        if _damo_subproc.avail_cmd('perf'):
            tracer = 'perf'
        elif _damo_subproc.avail_cmd('trace-cmd'):
            tracer = 'trace-cmd'
    else:
        tracer = args.tracer

    if tracer == 'perf':
        cmd = [tracer, 'trace']
    else:
        cmd = [tracer, 'stream']

    for trace_event in events:
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
    parser.add_argument(
            '--event', choices=list(damon_trace_events) + ['all'], nargs='+',
            default='all',
            help='events to trace')
    parser.add_argument(
            '--no_event', choices=list(damon_trace_events), nargs='+',
            help='events to skip tracing')
    parser.add_argument('--tracer', choices=['perf', 'trace-cmd'],
                        help='tracer command to use')
    parser.add_argument('--input', '-i', metavar='<file>',
                        help='trace record file')
