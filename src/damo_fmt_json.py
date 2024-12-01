# SPDX-License-Identifier: GPL-2.0

"""
Convert args to DAMON json input.
"""

import json

import _damo_deprecation_notice
import _damon
import _damon_args

def main(args):
    _damo_deprecation_notice.deprecated(
            feature='"damo fmt_json"', deadline='2024-12',
            do_exit=True, exit_code=1,
            additional_notice='Use "damo args damon --format json" instead.')
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

    if args.schemes_only:
        schemes = []
        for kdamond in kdamonds:
            for ctx in kdamond.contexts:
                schemes += ctx.schemes
        print(json.dumps([s.to_kvpairs(args.raw) for s in schemes], indent=4))
        return
    print(json.dumps({'kdamonds': [k.to_kvpairs(args.raw) for k in kdamonds]},
        indent=4))

def set_argparser(parser):
    _damon_args.set_argparser(parser, add_record_options=False, min_help=True)
    parser.add_argument('--schemes_only', action='store_true',
            help='print schemes part only')
    parser.add_argument('--raw', action='store_true',
            help='print numbers in machine friendly raw form')
