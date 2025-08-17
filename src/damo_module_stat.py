# SPDX-License-Identifier: GPL-2.0

import os

import _damo_fmt_str
import _damon

def cum_mem_pct_of(percentiles, idle_sec):
    if idle_sec < percentiles[0]:
        return 0.0
    for cum_mem_pct, iter_idle_second in enumerate(percentiles):
        if iter_idle_second == idle_sec:
            return cum_mem_pct
        if iter_idle_second > idle_sec:
            # assume linear distribution
            before_idle_sec = percentiles[cum_mem_pct - 1]
            before_to_target_idle_sec = idle_sec - before_idle_sec
            before_to_current = iter_idle_second - before_idle_sec
            the_ratio = before_to_target_idle_sec / before_to_current
            return cum_mem_pct - 1 + the_ratio
    return 100.0

def mem_sz_of_idle_time_range(percentiles, idle_sec_range):
    a = cum_mem_pct_of(percentiles, idle_sec_range[1])
    b = cum_mem_pct_of(percentiles, idle_sec_range[0])
    return a - b

def do_pr_idle_time_mem_sz(percentiles, gran, raw_number):
    # percentiles is 101 values list, each meaning p0 to p100 in seconds.
    # gran is the granularity of idle time to memory size
    min_idle_sec = percentiles[0]
    max_idle_sec = percentiles[-1]
    idle_time_interval = (max_idle_sec - min_idle_sec) / gran

    idle_sec_range = [min_idle_sec - 1, min_idle_sec + idle_time_interval]
    rows = []
    max_time_column_len = 0
    while idle_sec_range[0] < max_idle_sec:
        rows.append([
            _damo_fmt_str.format_time_sec(idle_sec_range[1], raw_number),
            _damo_fmt_str.format_percent(
                mem_sz_of_idle_time_range(percentiles, idle_sec_range),
                raw_number)])

        time_col_len = len(rows[-1][0])
        if time_col_len > max_time_column_len:
            max_time_column_len = time_col_len

        idle_sec_range[0] += idle_time_interval
        idle_sec_range[1] += idle_time_interval
    for row in rows:
        print('%s%s%s' % (
            row[0], ' ' * (max_time_column_len + 4 - len(row[0])), row[1]))

def pr_idle_time_mem_sz(nr_lines, raw_number):
    param_dir = '/sys/module/damon_stat/parameters'
    with open(os.path.join(param_dir, 'memory_idle_ms_percentiles'), 'r') as f:
        idle_sec_percentiles = [int(x) / 1000 for x in f.read().split(',')]
    do_pr_idle_time_mem_sz(idle_sec_percentiles, nr_lines, raw_number)

def pr_idle_time_percentiles(range_vals, raw_number):
    param_dir = '/sys/module/damon_stat/parameters'
    with open(os.path.join(param_dir, 'memory_idle_ms_percentiles'), 'r') as f:
        idle_sec_percentiles = [int(x) / 1000 for x in f.read().split(',')]

    start, end, interval = range_vals
    percentile = start
    while percentile < end:
        print('%3d' % percentile,
              _damo_fmt_str.format_time_sec(
                  idle_sec_percentiles[percentile], raw_number))
        percentile += interval

def handle_read_write(args):
    module_name = args.module_name
    param_dir = '/sys/module/damon_%s/parameters' % module_name
    if args.action == 'read':
        if args.parameter == 'idle_time_mem_sz':
            pr_idle_time_mem_sz(args.idle_time_mem_sz_lines, args.raw_number)
        elif args.parameter == 'idle_time_percentiles':
            pr_idle_time_percentiles(args.idle_time_percentiles_range,
                                     args.raw_number)
        elif args.parameter is not None:
            with open(os.path.join(param_dir, args.parameter), 'r') as f:
                print(f.read().strip())
        else:
            for param in os.listdir(param_dir):
                with open(os.path.join(param_dir, param), 'r') as f:
                    print('%s: %s' % (param, f.read().strip()))
    elif args.action == 'write':
        if len(args.parameter_value) % 2 != 0:
            print('wrong paramter_value')
            exit(1)

        for i in range(0, len(args.parameter_value), 2):
            param_name = args.parameter_value[i]
            param_val = args.parameter_value[i + 1]
            with open(os.path.join(param_dir, param_name), 'w') as f:
                f.write(param_val)

def main(args):
    handle_read_write(args)

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='action', dest='action', metavar='<action>')
    subparsers.required = True

    parser_read = subparsers.add_parser('read', help='read parameters')
    parser_read.add_argument(
            'parameter', metavar='<parameter name>', nargs='?',
            help='parameter to read.')
    parser_read.add_argument(
            '--idle_time_mem_sz_lines', default=100, type=int,
            help='number of lines for idle time to memory size output')
    parser_read.add_argument(
            '--idle_time_percentiles_range', default=[0, 101, 1], type=int,
            nargs=3,
            help='idle time percentiles print range (start, end, interval)')
    parser_read.add_argument('--raw_number', action='store_true',
                             help='print number in raw form')

    parser_write = subparsers.add_parser('write', help='write parameters')
    parser_write.add_argument(
            'parameter_value', metavar=('<parameter name> <value>'), nargs='+',
            help='name of the parameter and the value to write')
    return parser
