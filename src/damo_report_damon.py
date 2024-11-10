# SPDX-License-Identifier: GPL-2.0

"""
Show status of DAMON.
"""

import collections
import json
import random
import time

import _damo_fmt_str
import _damon
import _damon_args

def read_kdamonds_from_file(input_file):
    # returns read kdamonds and error
    try:
        with open(input_file, 'r') as f:
            kdamonds = [_damon.Kdamond.from_kvpairs(kvp)
                        for kvp in json.load(f)]
    except Exception as e:
        return None, 'reading %s failed (%s)' % (input_file, e)
    return kdamonds, None

def pr_damon_parameters(input_file, json_format, raw_nr):
    if input_file is None:
        kdamonds = _damon.current_kdamonds()
    else:
        kdamonds, err = read_kdamonds_from_file(input_file)
        if err is not None:
            print(err)
            exit(1)

    for k in kdamonds:
        for c in k.contexts:
            for s in c.schemes:
                s.stats = None
                s.tried_regions = None

    pr_kdamonds(kdamonds, json_format, raw_nr, show_cpu=False)

def update_pr_schemes_stats(input_file, json_format, raw_nr,
                            damos_stat_fields):
    if input_file is None:
        err = _damon.update_schemes_stats()
        if err:
            print(err)
            return
        kdamonds = _damon.current_kdamonds()
    else:
        kdamonds, err = read_kdamonds_from_file(input_file)
        if err is not None:
            print(err)
            exit(1)

    stats = []
    for kd_idx, kdamond in enumerate(kdamonds):
        for ctx_idx, ctx in enumerate(kdamond.contexts):
            for scheme_idx, scheme in enumerate(ctx.schemes):
                indices = {
                        'kdamond':kd_idx, 'context': ctx_idx, 'scheme': scheme_idx}
                stat_kvpair = scheme.stats.to_kvpairs(raw_nr)
                if damos_stat_fields:
                    filtered_stat_kvpair = collections.OrderedDict()
                    for k in damos_stat_fields:
                        filtered_stat_kvpair[k] = stat_kvpair[k]
                    stat_kvpair = filtered_stat_kvpair
                stats.append([indices, stat_kvpair])

    if json_format:
        print(json.dumps(stats, indent=4))
        return

    for indices, stat_kvpair in stats:
        if len(stats) > 1:
            print('kdamond %d / context %d / scheme %d' % (indices['kdamond'],
                indices['context'], indices['scheme']))
        for k, v in stat_kvpair.items():
            if len(stat_kvpair.keys()) > 1:
                print('%s: %s' % (k, v))
            else:
                print('%s' % v)
        if len(stats) > 1:
            print()

def pr_kdamonds_summary(input_file, json_format, raw_nr, show_cpu):
    if input_file is None:
        kdamonds = _damon.current_kdamonds()
    else:
        kdamonds, err = read_kdamonds_from_file(input_file)
        if err is None:
            print(err)
            exit(1)
    summary = [k.summary_str(show_cpu) for k in kdamonds]
    if json_format:
        print(json.dumps(summary, indent=4))
        return
    if len(summary) == 1:
        print(summary)
    for idx, line in enumerate(summary):
        print('%d\t%s' % (idx, line))

def pr_kdamonds(kdamonds, json_format, raw_nr, show_cpu):
    if json_format:
        print(json.dumps([k.to_kvpairs(raw_nr) for k in kdamonds], indent=4))
    else:
        for idx, k in enumerate(kdamonds):
            print('kdamond %d' % idx)
            print(_damo_fmt_str.indent_lines( k.to_str(raw_nr, show_cpu), 4))

def main(args):
    _damon.ensure_root_and_initialized(args)

    if args.damon_params:
        return pr_damon_parameters(args.input_file, args.json, args.raw)

    if args.kdamonds_summary:
        return pr_kdamonds_summary(args.input_file, args.json, args.raw,
                                   args.show_cpu_usage)

    if args.damos_stats:
        return update_pr_schemes_stats(args.input_file, args.json, args.raw,
                                       args.damos_stat_fields)

    if args.input_file is None:
        kdamonds, err = _damon.update_read_kdamonds(
                nr_retries=5, update_stats=True, update_tried_regions=True,
                update_quota_effective_bytes=True)
        if err != None:
            print('cannot update and read kdamonds: %s' % err)
            exit(1)
    else:
        kdamonds, err = read_kdamonds_from_file(args.input_file)
        if err is not None:
            print(err)
            exit(1)
    pr_kdamonds(kdamonds, args.json, args.raw, args.show_cpu_usage)

def set_argparser(parser):
    parser.add_argument('--json', action='store_true', default=False,
            help='print output in json format')
    parser.add_argument('--raw', action='store_true', default=False,
            help='print raw numbers')
    parser.add_argument('--show_cpu_usage', action='store_true', default=False,
            help='show cpu usage for kdamond')
    parser.add_argument('--kdamonds_summary', action='store_true',
            help='print kdamond summary only')
    parser.add_argument('--damos_stats', action='store_true',
            help='print DAMOS scheme stats only')
    parser.add_argument('--damos_stat_fields', metavar='<stat field name>',
            choices=['nr_tried', 'sz_tried', 'nr_applied', 'sz_applied',
                'qt_exceeds'], nargs='+',
            help='DAMOS stat fields to print')
    parser.add_argument('--damon_params', action='store_true',
            help='print entered DAMON parameters only')
    parser.add_argument(
            '--input_file', metavar='<file>', help=' '.join([
                'A json file containing the status of kdamonds to show.',
                'If this is not given, capture and show status of',
                'current kdamonds.']))
    _damon_args.set_common_argparser(parser)
    return parser
