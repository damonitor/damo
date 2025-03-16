# SPDX-License-Identifier: GPL-2.0

import collections
import json

import _damo_yaml
import _damon
import _damon_args
import damo_report_damon

def main(args):
    _damon.ensure_root_permission()

    kdamonds, err = _damon_args.kdamonds_for(args)
    if err:
        print('invalid arguments (%s)' % err)
        exit(1)

    for k in kdamonds:
        for c in k.contexts:
            for s in c.schemes:
                s.stats = None
                s.tried_regions = None

    if args.add is not None:
        old_kdamonds, err = _damon_args.kdamonds_from_json_arg(args.add)
        if err is not None:
            print('cannot parse %s (%s)' % (args.add, err))
            exit(1)
        kdamonds = old_kdamonds + kdamonds

    if args.remove is not None:
        filepath = args.remove[0]
        kdamond_idx = int(args.remove[1])
        kdamonds, err = _damon_args.kdamonds_from_json_arg(filepath)
        if err is not None:
            print('cannot parse %s (%s)' % (filepath, err))
            exit(1)
        del kdamonds[kdamond_idx]

    if args.replace is not None:
        filepath = args.replace[0]
        kdamond_idx = int(args.replace[1])
        old_kdamonds, err = _damon_args.kdamonds_from_json_arg(filepath)
        if err is not None:
            print('cannot parse %s (%s)' % (filepath, err))
            exit(1)
        old_kdamonds[kdamond_idx] = kdamonds[0]
        kdamonds = old_kdamonds

    kvpairs = {'kdamonds':
               [k.to_kvpairs(args.raw, args.omit_defaults, params_only=True)
                for k in kdamonds]}
    if args.format == 'report':
        if args.out is not None:
            print('--out and report format cannot be used together')
            exit(1)
        damo_report_damon.pr_kdamonds(
                kdamonds, json_format=False, raw_nr=args.raw, show_cpu=False)
        return

    if args.format == 'json':
        text = json.dumps(kvpairs, indent=4)
    elif args.format == 'yaml':
        text, err = _damo_yaml.dump(kvpairs)
        if err is not None:
            print('yaml dump failed (%s)' % err)
            exit(1)
    if args.out is None:
        print(text)
    else:
        with open(args.out, 'w') as f:
            f.write(text)

def set_argparser(parser):
    _damon_args.set_damon_params_argparser(parser, min_help=False)
    parser.description = ' '.join([
        'format DAMON parameters'])
    parser.add_argument(
            '--format', choices=['json', 'yaml', 'report'], default='json',
            help='format of the output')
    parser.add_argument(
            '--raw', action='store_true',
            help='print numbers in machine friendly raw form')
    parser.add_argument(
            '--add', metavar='<file>',
            help='add DAMON parameters to those of a given file')
    parser.add_argument(
            '--remove', nargs=2, metavar=('<file>', '<kdamond index>'),
            help='remove a kdamond of given index from those of the given file')
    parser.add_argument(
            '--replace', nargs=2, metavar=('<file>', '<kdamond index>'),
            help='replace a kdamond of given index in the given file')
    parser.add_argument(
            '--out', metavar='<file>', help='save the output to the given file')
    parser.add_argument( '--omit_defaults', action='store_true',
                        help='omit default parameters')
