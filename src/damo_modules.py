# SPDX-License-Identifier: GPL-2.0

import _damo_subcmds
import damo_lru_sort
import damo_reclaim

subcmds = [
        _damo_subcmds.DamoSubCmd(
            name='reclaim', module=damo_reclaim, msg='DAMON_RECLAIM'),
        _damo_subcmds.DamoSubCmd(
            name='lru_sort', module=damo_lru_sort, msg='DAMON_LRU_SORT'),
        ]

def main(args):
    for subcmd in subcmds:
        if subcmd.name == args.module_name:
            subcmd.execute(args)

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='DAMON module name', dest='module_name',
            metavar='<module name>',
            help='the name of DAMON module to control')
    subparsers.required = True

    for subcmd in subcmds:
        subcmd.add_parser(subparsers)
