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
    if 'sysfs_features' in args.print or 'all' in args.print:
        print('Sysfs avail DAMON features')
        for feature in sysinfo.avail_damon_features:
            if feature.name.startswith('sysfs/'):
                pr_feature(feature)
    if 'debugfs_features' in args.print or 'all' in args.print:
        print('Debugfs avail DAMON features')
        for feature in sysinfo.avail_damon_features:
            if feature.name.startswith('debugfs/'):
                pr_feature(feature)
    if 'trace_features' in args.print or 'all' in args.print:
        print('Avail DAMON trace features')
        for feature in sysinfo.avail_damon_features:
            if feature.name.startswith('trace/'):
                pr_feature(feature)
    if 'modules' in args.print or 'all' in args.print:
        print('Avail DAMON modules')
        for feature in sysinfo.avail_damon_features:
            if feature.name.startswith('module/'):
                pr_feature(feature)

def set_argparser(parser):
    parser.add_argument(
            '--print', nargs='+',
            choices=['versions', 'fs_info', 'trace_cmd_info', 'perf_info',
                     'sysfs_features', 'debugfs_features', 'trace_features',
                     'modules', 'all'],
            default=['versions'], help='info to print')
    parser.add_argument('--invalidate_cache', action='store_true',
                        help='invalidate cached sysinfo')
    return parser
