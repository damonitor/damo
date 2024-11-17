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
        kdamonds, err = _damon_args.kdamonds_from_json_arg(args.remove[0])
        if err is not None:
            print('cannot parse %s (%s)' % (args.add, err))
            exit(1)
        del kdamonds[kdamond_idx]

    kvpairs = {'kdamonds': [k.to_kvpairs(args.raw) for k in kdamonds]}
    if args.format == 'json':
        print(json.dumps(kvpairs, indent=4))
    elif args.format == 'yaml':
        text, err = _damo_yaml.dump(kvpairs)
        if err is not None:
            print('yaml dump failed (%s)' % err)
            exit(1)
        print(text)
    elif args.format == 'report':
        damo_report_damon.pr_kdamonds(
                kdamonds, json_format=False, raw_nr=args.raw, show_cpu=False)

def set_argparser(parser):
    _damon_args.set_argparser(parser, add_record_options=False, min_help=False)
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
