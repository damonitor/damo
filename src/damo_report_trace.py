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
            return f.read(), None
    except Exception as e:
        return None, '%s' % e

def read_trace_record(record_file):
    '''
    Supports outputs from
    - 'perf record',
    - 'trace-cmd record', and
    - 'damo report trace --output <file>'.
    '''
    trace_text, perf_err = read_perf_record(record_file)
    if perf_err is None:
        return trace_text, 'perf-script', None
    trace_text, trace_cmd_err = read_trace_cmd_record(record_file)
    if trace_cmd_err is None:
        return trace_text, 'trace-cmd-report', None
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

def get_trace_fields(fields, trace_text_format, trace_name):
    if trace_text_format == 'damo-report-trace-perf':
        #   3128.371 kdamond.0/764 damon:damon_aggregated(trace fields)
        trace_fields = fields[2:]
        trace_fields[0] = trace_fields[0][len(trace_name) + 1:]
        trace_fields[-1] = trace_fields[-1][:-1]
    else:
        # <...>-764   [001] .....  1394.412830: damon_region_aggregated: trace fields
        trace_fields = fields[3:]
    return trace_fields

region_idx = 0
def pr_damon_aggregated(fields, trace_text_format, max_cols):
    trace_fields = get_trace_fields(
            fields, trace_text_format, 'damon:damon_aggregated')
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
    pr_wrapped(' '.join(fields[:2] + ['damon_aggregated', trace_text]),
               max_cols)

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

def fmt_damon_region_aggregated(fields, trace_text_format):
    trace_fields = get_trace_fields(
            fields, trace_text_format, 'damon:damon_region_aggregated')
    trace_text = fmt_damon_region_aggregated_trace(trace_fields)
    return ' '.join(fields[:2] + ['damon_region_aggregated', trace_text])

def pr_damon_region_aggregated(fields, trace_text_format, max_cols):
    pr_wrapped(
            fmt_damon_region_aggregated(fields, trace_text_format), max_cols)

def pr_damos_before_apply(fields, trace_text_format, max_cols):
    trace_fields = get_trace_fields(
            fields, trace_text_format, 'damon:damos_before_apply')
    # trace_fields: ctx_idx=0 scheme_idx=0 target_idx=0 nr_regions=11 1234-5678: 10 45
    context_idx = int(trace_fields[0].split('=')[1])
    scheme_idx = int(trace_fields[1].split('=')[1])
    target_idx = int(trace_fields[2].split('=')[1])
    nr_regions = int(trace_fields[3].split('=')[1])
    start = int(trace_fields[4].split('-')[0])
    end = int(trace_fields[4].split('-')[1][:-1])
    nr_accesses = int(trace_fields[5])
    age = int(trace_fields[6])

    trace_text = '%d %d %d %d %s (%s) %d %d' % (
            context_idx, scheme_idx, target_idx, nr_regions,
            _damo_fmt_str.format_sz_accurate(start, machine_friendly=False),
            _damo_fmt_str.format_sz_accurate(
                end - trace_data['start'], machine_friendly=False),
            nr_accesses, age)
    pr_wrapped(' '.join(fields[:2] + ['damos_before_apply', trace_text]),
               max_cols)

def pr_damos_stat(fields, trace_text_format, max_cols):
    trace_fields = get_trace_fields(
            fields, trace_text_format, 'damon:damos_stat')
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

    trace_text = '%d %d %s %s %s %s %s %s %s' % (
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
    pr_wrapped(' '.join(fields[:2] + ['damos_stat', trace_text]), max_cols)

def pr_trace_line(line, raw, trace_text_format, max_cols):
    if raw is True:
        print(line)
    fields = line.split()
    if trace_text_format == 'perf-script':
        fields = [fields[1]] + fields[3:]
        event = fields[2]
        event = event[len('damon:'):]
        fields[2] = event

        kdamond_pid = fields[0]
        timestamp = fields[1]
    elif trace_text_format == 'trace-cmd-report':
        fields = [fields[0]] + fields[3:]

        kdamond_pid = fields[0].split('-')[-1]
        timestamp = fields[1]
    elif trace_text_format == 'damo-report-trace-perf':
        fields = fields
        event = fields[2]
        event = event[len('damon:'):]
        fields[2] = event

        kdamond_pid = fields[1].split('/')[-1]
        timestamp = fields[0]
    elif trace_text_format == 'damo-report-trace-trace-cmd':
        fields = [fields[0]] + fields[3:]

        kdamond_pid = fields[0].split('-')[-1]
        timestamp = fields[1]

    fields[0] = timestamp
    fields[1] = kdamond_pid

    if fields[2].startswith('damon_region_aggregated'):
        pr_damon_region_aggregated(fields, trace_text_format, max_cols)
        return
    if fields[2].startswith('damon_aggregated'):
        pr_damon_aggregated(fields, trace_text_format, max_cols)
        return
    if fields[2].startswith('damos_before_apply'):
        pr_damos_before_apply(fields, trace_text_format, max_cols)
        return
    if fields[2].startswith('damos_stat_after_apply_interval'):
        pr_damos_stat(fields, trace_text_format, max_cols)
        return
    pr_wrapped(' '.join(fields), max_cols)

def report_recorded_trace(args):
    trace_text, trace_text_format, err = read_trace_record(args.input)
    if err is not None:
        print(err)
        return -1

    events = get_events_to_show(args.event, args.no_event)

    for line in trace_text.split('\n'):
        fields = line.split()
        if trace_text_format in ['perf-script', 'trace-cmd-report']:
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
        pr_trace_line(line, args.raw, trace_text_format, args.max_cols)

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
    while True:
        output = tracer_pipe.stdout.readline()
        if not output and tracer_pipe.poll() is not None:
            break
        output = output.decode()
        pr_trace_line(output, args.raw, 'damo-report-trace-%s' % tracer,
                      args.max_cols)
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
