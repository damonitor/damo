# SPDX-License-Identifier: GPL-2.0

"""
Record monitored data access patterns.
"""

import json
import os
import signal
import subprocess
import time

import _damo_records
import _damon
import _damon_args

class DataForCleanup:
    kdamonds_idxs = None
    orig_kdamonds = None
    record_handle = None

data_for_cleanup = DataForCleanup()

cleaning = False

def cleanup_exit(exit_code):
    global cleaning
    if cleaning == True:
        return
    cleaning = True
    if data_for_cleanup.kdamonds_idxs != None:
        # ignore returning error, as kdamonds may already finished
        _damon.turn_damon_off(data_for_cleanup.kdamonds_idxs)
        err = _damon.stage_kdamonds(data_for_cleanup.orig_kdamonds)
        if err:
            print('failed restoring previous kdamonds setup (%s)' % err)

    if data_for_cleanup.record_handle:
        _damo_records.finish_recording(data_for_cleanup.record_handle)

    exit(exit_code)

def sighandler(signum, frame):
    print('\nsignal %s received' % signum)
    cleanup_exit(signum)

def handle_args(args):
    if _damon.any_kdamond_running() and not args.deducible_target:
        args.deducible_target = 'ongoing'

    args.output_permission, err = _damo_records.parse_file_permission_str(
            args.output_permission)
    if err != None:
        print('wrong --output permission (%s) (%s)' %
                (args.output_permission, err))
        exit(1)

    # backup duplicate output file
    if os.path.isfile(args.out):
        os.rename(args.out, args.out + '.old')

    if args.footprint is True:
        footprint_file_path = '%s.mem_footprint' % args.out
        if os.path.isfile(footprint_file_path):
            os.rename(footprint_file_path, footprint_file_path + '.old')

    err = _damo_records.set_perf_path(args.perf_path)
    if err != None:
        print(err)
        exit(-3)

def mk_handle(args, kdamonds, monitoring_intervals):
    if args.schemes_target_regions == False:
        tracepoint = _damo_records.perf_event_damon_aggregated
    else:
        tracepoint = _damo_records.perf_event_damos_before_apply

    handle = _damo_records.RecordingHandle(
            # for access pattern monitoring
            tracepoint=tracepoint, file_path=args.out,
            file_format=args.output_type,
            file_permission=args.output_permission,
            monitoring_intervals=monitoring_intervals,
            # for perf profile
            do_profile=args.profile is True,
            # for children processes recording and memory footprint
            kdamonds=kdamonds, add_child_tasks=args.include_child_tasks,
            record_mem_footprint=args.footprint,
            record_vmas=args.vmas, timeout=args.timeout)

    if args.snapshot is not None:
        handle.tracepoint = None
        tried_regions_of = None
        if args.schemes_target_regions:
            tried_regions_of = []
            for kidx, kd in enumerate(kdamonds):
                for cidx, ctx in enumerate(kd.contexts):
                    for sidx, scheme in enumerate(ctx.schemes):
                        tried_regions_of.append([kidx, cidx, sidx])
        handle.snapshot_request = _damo_records.RecordGetRequest(
                tried_regions_of=tried_regions_of, record_file=None,
                record_filter=None, total_sz_only=False,
                dont_merge_regions=False)
        handle.snapshot_interval_sec = args.snapshot[0]
        handle.snapshot_count = args.snapshot[1]

    return handle

def main(args):
    global data_for_cleanup

    _damon.ensure_root_and_initialized(args)

    handle_args(args)

    # Setup for cleanup
    data_for_cleanup.orig_kdamonds = _damon.current_kdamonds()
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)

    # Now the real works
    if not _damon_args.is_ongoing_target(args):
        err, kdamonds = _damon_args.turn_damon_on(args)
        if err:
            print('could not turn DAMON on (%s)' % err)
            cleanup_exit(-2)
        data_for_cleanup.kdamonds_idxs = ['%d' % idx
                for idx, k in enumerate(kdamonds)]
        # TODO: Support multiple kdamonds, multiple contexts
        monitoring_intervals = kdamonds[0].contexts[0].intervals
        now_kdamonds = _damon.current_kdamonds()
        kdamonds[0].pid = now_kdamonds[0].pid
    else:
        if not _damon.any_kdamond_running():
            print('DAMON is not turned on')
            exit(1)

        # TODO: Support multiple kdamonds, multiple contexts
        monitoring_intervals = data_for_cleanup.orig_kdamonds[
                0].contexts[0].intervals
        kdamonds = data_for_cleanup.orig_kdamonds

    record_handle = mk_handle(args, kdamonds, monitoring_intervals)

    data_for_cleanup.record_handle = record_handle

    print('Press Ctrl+C to stop')
    _damo_records.start_recording(record_handle)
    cleanup_exit(0)

def set_argparser(parser):
    _damon_args.set_argparser(parser, add_record_options=True, min_help=True)
    parser.add_argument('--output_type',
                        choices=_damo_records.file_types,
                        default=_damo_records.file_type_json_compressed,
                        help='output file\'s type')
    parser.add_argument('--output_permission', type=str, default='600',
                        help='permission of the output file')
    parser.add_argument('--perf_path', type=str, default='perf',
                        help='path of perf tool ')
    parser.add_argument('--exclude_child_tasks', action='store_false',
                        dest='include_child_tasks',
                        help='do not record access of child processes')
    parser.add_argument('--include_child_tasks', action='store_true',
                        help='record accesses of child processes')
    parser.add_argument('--schemes_target_regions', action='store_true',
                        help='record schemes tried to be applied regions')
    parser.add_argument('--no_profile', action='store_false', dest='profile',
                        help='do not record profiling information')
    parser.add_argument('--no_footprint', action='store_false',
                        dest='footprint',
                        help='do not record memory footprint')
    parser.add_argument('--no_vmas', action='store_false', dest='vmas',
                        help='record virtual memory areas (/proc/<pid>/maps)')
    parser.add_argument('--snapshot', metavar=('<delay>', '<count>'), nargs=2,
                        type=float, help='record accesses as snapshots')
    parser.add_argument('--timeout', type=float, metavar='<seconds>',
                        help='stop recording after the given seconds')
    return parser
