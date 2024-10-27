# SPDX-License-Identifier: GPL-2.0

import json
import os
import sys

import _damo_deprecation_notice
import _damo_fmt_str
import _damo_print
import _damo_records
import damo_report_access

def filter_snapshots(records, start_time_sec, end_time_sec):
    for record in records:
        if len(record.snapshots) == 0:
            continue
        base_time = record.snapshots[0].start_time
        filtered_snapshots = []
        for snapshot in record.snapshots:
            offset_sec = (snapshot.start_time - base_time) / 1000000000
            if offset_sec < start_time_sec:
                continue
            if offset_sec > end_time_sec:
                break
            filtered_snapshots.append(snapshot)
        record.snapshots = filtered_snapshots

def pr_records(args, records):
    lines = []
    if args.duration:
        filter_snapshots(records, args.duration[0], args.duration[1])

    if args.json:
        _damo_print.pr_with_pager_if_needed(
                json.dumps([r.to_kvpairs(args.raw_number) for r in records],
                           indent=4))
        return

    damo_report_access.pr_records_raw_form(records, args.raw_number)

def set_argparser(parser):
    parser.add_argument('--input', '-i', type=str, metavar='<file>',
            default='damon.data', help='input file name')
    parser.add_argument('--duration', type=float, metavar='<seconds>', nargs=2,
            help='start and end time offset for record to parse')
    parser.add_argument('--raw_number', action='store_true',
            help='use machine-friendly raw numbers')
    parser.add_argument('--json', action='store_true',
            help='print in json format')
    parser.description='Show raw data of the monitoring results record file'

def main(args):
    _damo_deprecation_notice.will_be_deprecated(
            feature='"damo report raw"', deadline='2025-01-27',
            additional_notice='Use "damo report access --raw_form" instead.')

    file_path = args.input

    if not os.path.isfile(file_path):
        print('input file (%s) is not exist' % file_path)
        exit(1)

    records, err = _damo_records.get_records(record_file=file_path)
    if err:
        print('parsing damon result file (%s) failed (%s)' %
                (file_path, err))
        exit(1)

    if len(records) == 0:
        print('no monitoring result in the file')
        exit(1)

    try:
        pr_records(args, records)
    except BrokenPipeError as e:
        # maybe user piped to 'less' like pager and quit from it
        pass
