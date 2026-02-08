# SPDX-License-Identifier: GPL-2.0

import _damo_sysinfo
import _damon

def pr_feature(feature):
    print('- %s (%s)' % (feature.name, feature.upstream_status))
    if feature.comments:
        print('  - %s' % feature.comments)

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

    for feature in sysinfo.avail_damon_features:
        if feature.name.startswith('interface/'):
            if 'all' not in args.print and 'interfaces' not in args.print:
                continue
        if feature.name.startswith('sysfs/'):
            if 'all' not in args.print and 'sysfs_features' not in args.print:
                continue
        if feature.name.startswith('debugfs/'):
            if 'all' not in args.print and \
                    'debugfs_features' not in args.print:
                continue
        if feature.name.startswith('trace/'):
            if 'all' not in args.print and 'trace_features' not in args.print:
                continue
        if feature.name.startswith('stat/'):
            if 'all' not in args.print and 'stat_features' not in args.print:
                continue
        if feature.name.startswith('lru_sort/'):
            if 'all' not in args.print and \
                    'lru_sort_features' not in args.print:
                continue
        pr_feature(feature)

def set_argparser(parser):
    parser.add_argument(
            '--print', nargs='+',
            choices=['versions', 'fs_info', 'trace_cmd_info', 'perf_info',
                     'sysfs_features', 'debugfs_features', 'trace_features',
                     'stat_features', 'lru_sort_features', 'interfaces',
                     'all'],
            default=['versions', 'interfaces'], help='info to print')
    parser.add_argument('--invalidate_cache', action='store_true',
                        help='invalidate cached sysinfo')
    return parser
