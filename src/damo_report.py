# SPDX-License-Identifier: GPL-2.0

import _damo_subcmds
import damo_heatmap
import damo_heats
import damo_nr_regions
import damo_report_access
import damo_report_footprint
import damo_report_holistic
import damo_report_kdamonds
import damo_report_profile
import damo_report_raw
import damo_report_times
import damo_wss

subcmds = [
        _damo_subcmds.DamoSubCmd(name='raw', module=damo_report_raw,
            msg='human readable raw data of access patterns'),
        _damo_subcmds.DamoSubCmd(name='access', module=damo_report_access,
            msg='access patterns'),
        _damo_subcmds.DamoSubCmd(name='heatmap', module=damo_heatmap,
            msg='heatmap of access patterns'),
        _damo_subcmds.DamoSubCmd(name='heats', module=damo_heats,
            msg='heats of regions'),
        _damo_subcmds.DamoSubCmd(name='wss', module=damo_wss,
            msg='working set size'),
        _damo_subcmds.DamoSubCmd(name='nr_regions', module=damo_nr_regions,
            msg='number of DAMON-regions'),
        _damo_subcmds.DamoSubCmd(name='profile', module=damo_report_profile,
            msg='hotspots for specific access pattern'),
        _damo_subcmds.DamoSubCmd(name='times', module=damo_report_times,
            msg='times of record having specific access pattern'),
        _damo_subcmds.DamoSubCmd(
            name='footprints', module=damo_report_footprint,
            msg='memory footprints'),
        _damo_subcmds.DamoSubCmd(
            name='holistic', module=damo_report_holistic,
            msg='holistic report'),
        _damo_subcmds.DamoSubCmd(
            name='kdamonds', module=damo_report_kdamonds,
            msg='current or recorded kdamonds'),
        ]

def main(args):
    for subcmd in subcmds:
        if subcmd.name == args.report_type:
            subcmd.execute(args)

def set_argparser(parser):
    subparsers = parser.add_subparsers(title='report type', dest='report_type',
            metavar='<report type>', help='the type of the report to generate')
    subparsers.required = True
    parser.description = "Format a report for 'damo record' generated data"

    for subcmd in subcmds:
        subcmd.add_parser(subparsers)
