# SPDX-License-Identifier: GPL-2.0

import _damo_sysinfo
import _damon
import _damon_features

def pr_feature(feature):
    print('- %s (%s)' % (feature.name, feature.upstream_status))
    if feature.comments:
        print('  - %s' % feature.comments)

def should_print_feature(args_print, category):
    if 'all' in args_print:
        return True
    if category in args_print:
        return True
    return False

def main(args):
    _damon.ensure_root_permission()
    if args.invalidate_cache:
        _damo_sysinfo.rm_sysinfo_file()
    sysinfo, err = _damo_sysinfo.get_sysinfo()
    if err is not None:
        print('getting sysinfo fail (%s)' % err)
        exit(1)
    if 'versions' in args.print or 'all' in args.print:
        print('damo version: %s' % sysinfo.damo_version)
        print('kernel version: %s' % sysinfo.kernel_version)
        version, err = sysinfo.infer_damon_version()
        if err is None:
            print('DAMON version: %s' % version)
    if 'fs_info' in args.print or 'all' in args.print:
        print('sysfs: %s' % sysinfo.sysfs_path)
        print('tracefs: %s' % sysinfo.tracefs_path)
        print('debugfs: %s' % sysinfo.debugfs_path)
    if 'trace_cmd_info' in args.print or 'all' in args.print:
        print('trace-cmd version: %s' % sysinfo.trace_cmd_version)
    if 'perf_info' in args.print or 'all' in args.print:
        print('perf path: %s' % sysinfo.perf_path)
        print('perf version: %s' % sysinfo.perf_version)

    features_to_print = []
    for feature in sysinfo.avail_damon_features:
        if feature.name.startswith('interface/'):
            if not should_print_feature(args.print, 'interfaces'):
                continue
        if feature.name.startswith('sysfs/'):
            if not should_print_feature(args.print, 'sysfs_features'):
                continue
        if feature.name.startswith('debugfs/'):
            if not should_print_feature(args.print, 'debugfs_features'):
                continue
        if feature.name.startswith('trace/'):
            if not should_print_feature(args.print, 'trace_features'):
                continue
        if feature.name.startswith('stat/'):
            if not should_print_feature(args.print, 'stat_features'):
                continue
        if feature.name.startswith('lru_sort/'):
            if not should_print_feature(args.print, 'lru_sort_features'):
                continue
        features_to_print.append(feature)
    if len(features_to_print) > 0:
        print('available DAMON features:')
        for f in features_to_print:
            pr_feature(f)

    if not should_print_feature(args.print, 'unavailable_features'):
        return

    unavail_features_to_print = []
    for feature in _damon_features.features_list:
        if not feature in sysinfo.avail_damon_features:
            unavail_features_to_print.append(feature)
    if len(unavail_features_to_print) > 0:
        print('unavailable DAMON features:')
        for f in unavail_features_to_print:
            pr_feature(f)

def set_argparser(parser):
    parser.add_argument(
            '--print', nargs='+',
            choices=['versions', 'fs_info', 'trace_cmd_info', 'perf_info',
                     'sysfs_features', 'debugfs_features', 'trace_features',
                     'stat_features', 'lru_sort_features', 'interfaces',
                     'unavailable_features',
                     'all'],
            default=['versions', 'interfaces'], help='info to print')
    parser.add_argument('--invalidate_cache', action='store_true',
                        help='invalidate cached sysinfo')
    return parser
