# SPDX-License-Identifier: GPL-2.0

import _damo_subcmds
import damo_nr_regions
import damo_report_access
import damo_report_damon
import damo_report_footprint
import damo_report_heatmap
import damo_report_holistic
import damo_report_profile
import damo_report_times
import damo_wss

subcmds = [
        _damo_subcmds.DamoSubCmd(name='access', module=damo_report_access,
            msg='access patterns'),
        _damo_subcmds.DamoSubCmd(
            name='damon', module=damo_report_damon,
            msg='current or recorded DAMON status'),
        _damo_subcmds.DamoSubCmd(
            name='holistic', module=damo_report_holistic,
            msg='holistic report'),
        _damo_subcmds.DamoSubCmd(name='heatmap', module=damo_report_heatmap,
            msg='heatmap of access patterns'),
        _damo_subcmds.DamoSubCmd(name='wss', module=damo_wss,
            msg='working set size'),
        _damo_subcmds.DamoSubCmd(
            name='footprints', module=damo_report_footprint,
            msg='memory footprints'),
        _damo_subcmds.DamoSubCmd(name='profile', module=damo_report_profile,
            msg='hotspot functions for specific access pattern'),
        _damo_subcmds.DamoSubCmd(name='times', module=damo_report_times,
            msg='times of record having specific access pattern'),
        _damo_subcmds.DamoSubCmd(name='nr_regions', module=damo_nr_regions,
            msg='number of DAMON-regions'),
        ]

def main(args):
    for subcmd in subcmds:
        if subcmd.name == args.report_type:
            subcmd.execute(args)

def set_argparser(parser):
    subparsers = parser.add_subparsers(title='report type', dest='report_type',
            metavar='<report type>', help='the type of the report to generate')
    subparsers.required = True

    for subcmd in subcmds:
        subcmd.add_parser(subparsers)
