# SPDX-License-Identifier: GPL-2.0

"""
Show status of DAMON.
"""

import json

import _damo_fmt_str
import _damon
import _damon_args

def main(args):
    if args.input_file is not None:
        with open(args.input_file, 'r') as f:
            kdamonds = [_damon.Kdamond.from_kvpairs(kvp) for kvp in json.load(f)]
    else:
        _damon.ensure_root_and_initialized(args)
        kdamonds = _damon.current_kdamonds()

    for idx, k in enumerate(kdamonds):
        print('kdamond %d' % idx)
        print(_damo_fmt_str.indent_lines(
            string=k.to_str(raw=False, show_cpu=False), indent_width=4))

def set_argparser(parser):
    parser.description = ' '.join([
        'Show status of currently staged kdamonds,',
        'or those of a record if the recorded file is given (--input_file).'])

    parser.add_argument('--input_file', metavar='<file>',
                        help='Kdamonds json file (e.g., damon.data.kdamonds)')
    _damon_args.set_common_argparser(parser)
    return parser
