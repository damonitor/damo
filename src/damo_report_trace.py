# SPDX-License-Identifier: GPL-2.0

import _damo_sysinfo

def main(args):
    print(args)
    print('WIP')

def set_argparser(parser):
    damon_tracepoints = list(
            _damo_sysinfo.tracepoint_to_feature_name_map.keys())
    parser.add_argument(
            '--event', choices=damon_tracepoints + ['all'], nargs='+',
            help='events to trace')
