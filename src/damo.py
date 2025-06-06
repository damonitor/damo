#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import argparse
import os

damo_dir = os.path.dirname(os.path.abspath(__file__))
os.sys.path.insert(0, damo_dir)

# on some distros, symlonk damo's directory is added to the os.sys.path,
# instead of the damo.py's directory.  In the case, using damo from local repo
# fails.  Check the case and modify os.sys.path, accordingly.
if not os.path.isfile(os.path.join(damo_dir, 'damo_version.py')):
    os.sys.path.insert(0, os.path.join(damo_dir, 'src'))

import sys

import _damo_subcmds
import damo_adjust
import damo_args
import damo_convert_record_format
import damo_diagnose
import damo_features
import damo_help
import damo_lru_sort
import damo_module
import damo_monitor
import damo_pa_layout
import damo_reclaim
import damo_record
import damo_record_info
import damo_replay
import damo_report
import damo_schemes
import damo_start
import damo_stop
import damo_tune
import damo_validate
import damo_version

def pr_damo_version(args_not_use):
    print(damo_version.__version__)

subcmds = [
        # DAMON control
        _damo_subcmds.DamoSubCmd(name='start', module=damo_start,
            msg='start DAMON with given parameters'),
        _damo_subcmds.DamoSubCmd(name='tune', module=damo_tune,
            msg='update input parameters of ongoing DAMON'),
        _damo_subcmds.DamoSubCmd(name='stop', module=damo_stop,
            msg='stop running DAMON'),

        # DAMON result recording and reporting/replaying
        _damo_subcmds.DamoSubCmd(name='record', module=damo_record,
            msg='record data accesses and additional information'),
        _damo_subcmds.DamoSubCmd(name='report', module=damo_report,
            msg='visualize the \'record\'-generated or snapshot data'),
        _damo_subcmds.DamoSubCmd(name='replay', module=damo_replay,
            msg='replay the recorded data accesses'),

        # DAMON modules control
        _damo_subcmds.DamoSubCmd(name='module', module=damo_module,
                                 msg='control DAMON kernel modules'),
        _damo_subcmds.DamoSubCmd(name='reclaim', module=damo_reclaim,
            msg='control DAMON_RECLAIM'),
        _damo_subcmds.DamoSubCmd(name='lru_sort', module=damo_lru_sort,
            msg='control DAMON_LRU_SORT'),

        # For convenient use of damo and DAMON
        _damo_subcmds.DamoSubCmd(
            name='help', module=damo_help,
            msg='provide help for given topics'),
        _damo_subcmds.DamoSubCmd(name='args',
            module=damo_args,
            msg='generate complex arguments for other commands'),
        _damo_subcmds.DamoSubCmd(name='version',
            module=_damo_subcmds.DamoSubCmdModule(None, pr_damo_version),
            msg='print the version number'),
        _damo_subcmds.DamoSubCmd(name='schemes', module=damo_schemes,
            msg='apply operation schemes'),
        _damo_subcmds.DamoSubCmd(name='monitor', module=damo_monitor,
            msg='repeat the recording and the reporting of data accesses'),
        _damo_subcmds.DamoSubCmd(name='features', module=damo_features,
            msg='list supported DAMON features in the kernel'),
        _damo_subcmds.DamoSubCmd(name='validate', module=damo_validate,
            msg='validate a given record result file'),
        _damo_subcmds.DamoSubCmd(name='adjust', module=damo_adjust,
            msg='adjust the record results with different monitoring attributes'),
        _damo_subcmds.DamoSubCmd(name='convert_record_format',
            module=damo_convert_record_format,
            msg='convert DAMON result record file\'s format'),
        _damo_subcmds.DamoSubCmd(name='record_info',
            module=damo_record_info,
            msg='print basic information of a data accesses record file'),
        _damo_subcmds.DamoSubCmd(name='diagnose',
            module=damo_diagnose,
            msg='generate a report on if DAMON is malfunctioning'),
        _damo_subcmds.DamoSubCmd(name='pa_layout',
            module=damo_pa_layout,
            msg='show physical address layout'),
        ]

class SubCmdHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        parts = super(argparse.RawDescriptionHelpFormatter,
                self)._format_action(action)
        # by default, the help message shows command metavar, like below.  Hide
        # it.
        #
        # $ ./damo -h
        # [...]
        # command:
        #   <command>  # <- This looks weird
        #     start               start DAMON with given parameters
        if action.nargs == argparse.PARSER:
            parts = '\n'.join(parts.split('\n')[1:])
        return parts

def main():
    parser = argparse.ArgumentParser(formatter_class=SubCmdHelpFormatter)
    parser.description = 'Control DAMON and show its results'

    subparser = parser.add_subparsers(title='command', dest='command',
            metavar='<command>')
    subparser.required = True

    for subcmd in subcmds:
        subcmd.add_parser(subparser)

    args = parser.parse_args()

    for subcmd in subcmds:
        if subcmd.name == args.command:
            subcmd.execute(args)

if __name__ == '__main__':
    main()
