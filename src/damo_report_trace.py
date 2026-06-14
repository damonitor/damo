# SPDX-License-Identifier: GPL-2.0

import datetime
import signal
import subprocess

import _damo_fmt_str
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
            text = f.read()
    except Exception as e:
        return None, None, '%s' % e
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return None, None, 'no header'
    header_lines = lines[:3]
    version_fields = header_lines[0].split()
    if len(version_fields) != 2:
        return None, None, 'wrong number of version header field (%d)' % (
                len(version_fields))
    if version_fields[0] != 'damo_report_trace_output_format_version:':
        return None, None, 'unexpected version header field (%s)' % (
                version_fields[0])
    tracer_fields = header_lines[2].split()
    if len(tracer_fields) != 2:
        return None, None, 'Wrong number of trace header field (%d)' % (
                len(tracer_fields))
    name, val = tracer_fields
    if name != 'damo_report_trace_output_tracer:':
        return None, None, 'Wrong tracer field name (%d)' % name
    if not val in ['perf', 'trace-cmd']:
        return None, None, 'Unsupported tracer (%d)' % val
    return text, val, None

def read_trace_record(record_file):
    '''
    Supports outputs from
    - 'perf record',
    - 'trace-cmd record', and
    - 'damo report trace --output <file>'.
    '''
    trace_text, perf_err = read_perf_record(record_file)
    if perf_err is None:
        return trace_text, 'perf', None
    trace_text, trace_cmd_err = read_trace_cmd_record(record_file)
    if trace_cmd_err is None:
        return trace_text, 'trace-cmd', None
    trace_text, tracer, text_err = read_damo_report_trace_output(record_file)
    if text_err is None:
        return trace_text, tracer, None
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

def pr_wrapped(line, max_cols):
    if len(line) <= max_cols:
        print(line)
        return
    fields = line.split()
    line_fields = []
    len_line = 0
    for field in fields:
        len_field = len(field)
        if len_line + len_field > max_cols:
            if len(line_fields) > 0:
                print(' '.join(line_fields))
                line_fields = []
            else:
                print(field)
            # indent second and later lines
            line_fields.append('  ')
            len_line = 2
        line_fields.append(field)
        len_line += len_field
        if len(line_fields) > 1:
            len_line += 1
    if len(line_fields) > 0:
        print(' '.join(line_fields))

def parse_trace_line(line, cmd):
    '''
    Input should be output from
    - 'perf script',
    - 'perf trace --libtraceevent_print',
    - 'trace-cmd report', or
    - 'trace-cmd stream'.

    Returns timestamp, proc, event and trace fields.

    Expected input formats for different commands are like below.

    perf script: <cmd> <pid> <cpu> <timestamp>: <event>: <trace outputs>
    perf trace: <timestamp> <cmd/pid> <event>(<trace outputs>)
    trace-cmd report:
        <cmd-pid> <cpu> <latency output> <timestamp>: <event>: <trace output>
    trace-cmd stream:
        <cmd-pid> <cpu> <latency output> <timestamp>: <event>: <trace output>

    On some versions of trace-cmd including 3.2-1ubuntu2, <latench output> is
    omitted.

    For example,
    (perf script)
    kdamond.0  129062 [004] 100952.251360: damon:damon_aggregated: target_id=0 nr_regions=11 8359534592-8371830784: 0 505
    (perf trace)
    3373.653 kthreadd/129062 damon:damon_aggregated(target_id=0 nr_regions=11 8344580096-8371830784: 0 33)
    (trace-cmd report)
    kdamond.0-129062 [005] ..... 101005.778382: damon_aggregated:     target_id=0 nr_regions=11 8360624128-8371830784: 0 974
    (trace-cmd stream)
    <...>-129062 [000] ..... 101029.459185: damon_aggregated:     target_id=0 nr_regions=11 8335224832-8371830784: 0 560
    (trace-cmd report of 3.2-1ubuntu2)
    kdamond.0-129062 [005] 101005.778382: damon_aggregated:     target_id=0 nr_regions=11 8360624128-8371830784: 0 974
    (trace-cmd stream of 3.2-1ubuntu2)
    <...>-129062 [000] 101029.459185: damon_aggregated:     target_id=0 nr_regions=11 8335224832-8371830784: 0 560
    '''

    fields = line.split()
    if cmd == 'perf-script':
        proc = '%s/%s' % (fields[0], fields[1])
        timestamp = fields[3][:-1]
        event = fields[4][:-1]
        trace_fields = fields[5:]
    elif cmd == 'perf-trace':
        #   3128.371 kdamond.0/764 damon:damon_aggregated(trace fields)
        timestamp, proc = fields[:2]
        event_first_trace_fields = fields[2].split('(')
        event = event_first_trace_fields[0]
        first_trace_field = '('.join(event_first_trace_fields[1:])
        remaining_trace_fields = fields[3:]
        if len(remaining_trace_fields) > 0:
            remaining_trace_fields[-1] = remaining_trace_fields[-1][:-1]
        trace_fields = [first_trace_field] + remaining_trace_fields
    elif cmd in ['trace-cmd-report', 'trace-cmd-stream']:
        # <...>-764   [001] .....  1394.412830: damon_region_aggregated: trace fields
        # In some versions of trace-cmd including 3.2-1ubuntu2,
        # <...>-764   [001] 1394.412830: damon_region_aggregated: trace fields
        proc = fields[0]
        if fields[2].endswith(':'):
            timestamp_idx = 2
        else:
            timestamp_idx = 3
        timestamp = fields[timestamp_idx][:-1]
        event = 'damon:%s' % fields[timestamp_idx + 1][:-1]
        trace_fields = fields[timestamp_idx + 2:]
    return timestamp, proc, event, trace_fields

region_idx = 0
def fmt_damon_aggregated(trace_fields):
    # trace_fields: target_id=0 nr_regions=11 8009068544-8372879360: 0 2740
    target_id = int(trace_fields[0].split('=')[1])
    nr_regions = int(trace_fields[1].split('=')[1])
    start = int(trace_fields[2].split('-')[0])
    end = int(trace_fields[2].split('-')[1][:-1])
    nr_accesses = int(trace_fields[3])
    if len(trace_fields) > 4:
        age = int(trace_fields[4])
    else:
        age = -1

    global region_idx
    trace_text = '%d %d/%d %s (%s) %d %d' % (
            target_id, region_idx, nr_regions,
            _damo_fmt_str.format_sz_accurate(start, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                end - start, machine_friendly=False),
            nr_accesses, age)
    region_idx += 1
    if region_idx == nr_regions:
        region_idx = 0
    return trace_text

region_aggregated_idx = 0
def fmt_damon_region_aggregated_trace(trace_fields):
    # trace_fields: target_id=0 nr_regions=11 8009068544-8372879360: 0 2740 probe_hits=14 00
    target_id = int(trace_fields[0].split('=')[1])
    nr_regions = int(trace_fields[1].split('=')[1])
    start = int(trace_fields[2].split('-')[0])
    end = int(trace_fields[2].split('-')[1][:-1])
    nr_accesses = int(trace_fields[3])
    age = int(trace_fields[4])
    if trace_fields[5] == 'probe_hits=':
        probe_hits = []
    else:
        probe_hits = [int(hits, 16) for hits in
                      [trace_fields[5].split('=')[1]] + trace_fields[6:]]

    global region_aggregated_idx
    trace_text = '%d %d/%d %s (%s) %d %d %s' % (
            target_id, region_aggregated_idx, nr_regions,
            _damo_fmt_str.format_sz_accurate(start, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                end - start, machine_friendly=False),
            nr_accesses, age, ' '.join(['%d' % h for h in probe_hits]))
    region_aggregated_idx += 1
    if region_aggregated_idx == nr_regions:
        region_aggregated_idx = 0
    return trace_text

def fmt_damos_before_apply(trace_fields):
    # trace_fields: ctx_idx=0 scheme_idx=0 target_idx=0 nr_regions=11 1234-5678: 10 45
    context_idx = int(trace_fields[0].split('=')[1])
    scheme_idx = int(trace_fields[1].split('=')[1])
    target_idx = int(trace_fields[2].split('=')[1])
    nr_regions = int(trace_fields[3].split('=')[1])
    start = int(trace_fields[4].split('-')[0])
    end = int(trace_fields[4].split('-')[1][:-1])
    nr_accesses = int(trace_fields[5])
    age = int(trace_fields[6])

    return '%d %d %d %d %s (%s) %d %d' % (
            context_idx, scheme_idx, target_idx, nr_regions,
            _damo_fmt_str.format_sz_accurate(start, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                end - start, machine_friendly=False),
            nr_accesses, age)

def fmt_damos_stat(trace_fields):
    context_idx = int(trace_fields[0].split('=')[1])
    scheme_idx = int(trace_fields[1].split('=')[1])
    nr_tried = int(trace_fields[2].split('=')[1])
    sz_tried = int(trace_fields[3].split('=')[1])
    nr_applied = int(trace_fields[4].split('=')[1])
    sz_applied = int(trace_fields[5].split('=')[1])
    if len(trace_fields) > 6:
        sz_ops_filter_passed = int(trace_fields[6].split('=')[1])
    else:
        sz_ops_filter_passed = -1
    if len(trace_fields) > 7:
        qt_exceeds = int(trace_fields[7].split('=')[1])
    else:
        qt_exceeds = -1
    if len(trace_fields) > 8:
        nr_snapshots = int(trace_fields[8].split('=')[1])
    else:
        nr_snapshots = -1

    return '%d %d %s %s %s %s %s %s %s' % (
            context_idx, scheme_idx,
            _damo_fmt_str.format_nr(nr_tried, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                sz_tried, machine_friendly=False),
            _damo_fmt_str.format_nr(nr_applied, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                sz_applied, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                sz_ops_filter_passed, machine_friendly=False),
            _damo_fmt_str.format_nr(qt_exceeds, machine_friendly=False),
             _damo_fmt_str.format_nr(nr_snapshots, machine_friendly=False)
             )

def pr_trace(timestamp, proc, event, trace_fields, max_cols):
    if event == 'damon:damon_region_aggregated':
        trace_text = fmt_damon_region_aggregated_trace(trace_fields)
    elif event == 'damon:damon_aggregated':
        trace_text = fmt_damon_aggregated(trace_fields)
    elif event == 'damon:damos_before_apply':
        trace_text = fmt_damos_before_apply(trace_fields)
    elif event == 'damon:damos_stat_after_apply_interval':
        trace_text = fmt_damos_stat(trace_fields)
    else:
        trace_text = ' '.join(trace_fields)
    pr_wrapped(' '.join([timestamp, proc, event, trace_text]), max_cols)

def report_recorded_trace(args):
    trace_text, tracer, err = read_trace_record(args.input)
    if err is not None:
        print(err)
        return -1

    events = get_events_to_show(args.event, args.no_event)

    if tracer == 'perf':
        cmd = 'perf-script'
    else:
        cmd = 'trace-cmd-report'

    for line in trace_text.strip().split('\n'):
        timestamp, proc, event, trace_fields = parse_trace_line(line, cmd)
        if not event in events:
            continue
        if args.raw:
            print(line)
        pr_trace(timestamp, proc, event, trace_fields, args.max_cols)

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
        cmd = [tracer, 'trace', '--libtraceevent_print']
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
    if tracer == 'perf':
        cmd = 'perf-trace'
    else:
        cmd = 'trace-cmd-stream'
    while True:
        output = tracer_pipe.stdout.readline()
        if not output and tracer_pipe.poll() is not None:
            break
        output = output.decode()

        timestamp, proc, event, trace_fields = parse_trace_line(output, cmd)
        if not event in events:
            continue
        if args.raw:
            print(output.strip())
        else:
            pr_trace(timestamp, proc, event, trace_fields, args.max_cols)

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
    parser.add_argument('--raw', action='store_true',
                        help='show raw trace output')
    parser.add_argument('--max_cols', type=int, default=100,
                        help='max columns per line')
