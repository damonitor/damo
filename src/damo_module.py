# SPDX-License-Identifier: GPL-2.0

import os

import _damo_subcmds
import damo_lru_sort
import damo_module_general
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

def set_subcmds(subcmds):
    for module in os.listdir('/sys/module'):
        if not module.startswith('damon_'):
            continue
        module_name = module[len('damon_'):]
        if module_name in ['reclaim', 'lru_sort']:
            continue
        subcmds.append(_damo_subcmds.DamoSubCmd(
            name=module_name, module=damo_module_general,
            msg='Control DAMON_%s' % module_name.upper()))

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='DAMON module name', dest='module_name',
            metavar='<module name>',
            help='the name of DAMON module to control')
    subparsers.required = True

    set_subcmds(subcmds)

    for subcmd in subcmds:
        subcmd.add_parser(subparsers)
