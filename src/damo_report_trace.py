# SPDX-License-Identifier: GPL-2.0

import datetime
import signal
import subprocess

import _damo_subproc
import _damo_sysinfo
import _damon

tracer_pipe = None
output_file = None

def signalhandler(signum, frame):
    print('signal %s received' % signum)
    if tracer_pipe:
        try:
            tracer_pipe.send_signal(signum)
            tracer_pipe.wait()
        except:
            pass
    if output_file:
        output_file.close()
    exit(0)

def read_perf_record(record_file):
    try:
        trace_text = subprocess.check_output(
                ['perf', 'script', '--force', '-i', record_file]).decode()
    except Exception as e:
        return None, '%s' % e
    return trace_text, None

def read_trace_cmd_record(record_file):
    try:
        trace_text = subprocess.check_output(
                ['trace-cmd', 'report', '-i', record_file]).decode()
    except Exception as e:
        return None, '%s' % e
    return trace_text, None

def read_damo_report_trace_output(output_file):
    try:
        with open(output_file, 'r') as f:
            return f.read(), None
    except Exception as e:
        return None, '%s' % e

def read_trace_record(record_file):
    trace_text, perf_err = read_perf_record(record_file)
    if perf_err is None:
        return trace_text, 'perf', None
    trace_text, trace_cmd_err = read_trace_cmd_record(record_file)
    if trace_cmd_err is None:
        return trace_text, 'trace-cmd', None
    trace_text, text_err = read_damo_report_trace_output(record_file)
    if text_err is None:
        tracer = trace_text.split('\n')[2].split()[1]
        return trace_text, 'damo-report-trace-%s' % tracer, None
    err = 'cannot parse %s via perf (%s), trace-cmd (%s), file read (%s)' % (
            record_file, perf_err, trace_cmd_err, text_err)
    return None, None, err

damon_trace_events = _damo_sysinfo.tracepoint_to_feature_name_map.keys()

def get_events_to_show(to_show, to_hide):
    events = []

    if 'all' in to_show:
        events = list(damon_trace_events)
    else:
        events = to_show
    if to_hide is not None:
        for event in to_hide:
            events.remove(event)
    return events

def report_recorded_trace(args):
    trace_text, trace_text_format, err = read_trace_record(args.input)
    if err is not None:
        print(err)
        return -1

    if args.event is None:
        print('--event is required')
        exit(1)

    events = get_events_to_show(args.event, args.no_event)

    for line in trace_text.split('\n'):
        fields = line.split()
        if trace_text_format in ['perf', 'trace-cmd']:
            # perf script and trace-cmd report puts the event name on fifth
            # field.
            # perf:
            #   kdamond.0  4452 [000] 82877.315633: damon:damon_aggregated: ...
            # trace-cmd:
            #   kdamond.0-264454 [007] ..... 92627.258073: damon_aggregated: ...
            if len(fields) < 5:
                continue
            event = fields[4][:-1]
        elif trace_text_format == 'damo-report-trace-perf':
            # 0.000 kdamond.0/83017 damon:damon_aggregated(nr_regions: 11, ...
            if len(fields) < 3:
                continue
            event = fields[2].split('(')[0]
        elif trace_text_format == 'damo-report-trace-trace-cmd':
            # <...>-83432 [006] ..... 71629.102757: damon_aggregated: ...
            if len(fields) < 5:
                continue
            event = 'damon:%s' % fields[4][:-1]

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

    events = get_events_to_show(args.event, args.no_event)

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

    global output_file
    if args.output is not None:
        output_file = open(args.output, 'w')
        output_file.write('damo_report_trace_output_format_version: 0\n')
        output_file.write('damo_report_trace_output_time: %s\n' %
                          datetime.datetime.now().timestamp())
        output_file.write('damo_report_trace_output_tracer: %s\n' % tracer)

    tracer_pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    while True:
        output = tracer_pipe.stdout.readline()
        if not output and tracer_pipe.poll() is not None:
            break
        output = output.decode()
        print(output, end='')
        if output_file is not None:
            output_file.write(output)

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
    parser.add_argument('--output', '-o', metavar='<file>',
                        help='save output to a file')
