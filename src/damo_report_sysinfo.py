# SPDX-License-Identifier: GPL-2.0

import _damo_sysinfo
import _damon

def pr_feature(feature):
    print('- %s (%s)' % (feature.name, feature.upstream_status))
    if feature.comments:
        print('  - %s' % feature.comments)

def main(args):
    _damon.ensure_root_permission()
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
    if 'sysfs_features' in args.print or 'all' in args.print:
        print('Sysfs avail DAMON features')
        for feature in sysinfo.avail_damon_sysfs_features:
            pr_feature(feature)
    if 'debugfs_features' in args.print or 'all' in args.print:
        print('Debugfs avail DAMON features')
        for feature in sysinfo.avail_damon_debugfs_features:
            pr_feature(feature)
    if 'trace_features' in args.print or 'all' in args.print:
        print('DAMON trace features')
        for feature in sysinfo.avail_damon_trace_features:
            pr_feature(feature)

def set_argparser(parser):
    parser.add_argument(
            '--print', nargs='+',
            choices=['versions', 'sysfs_features', 'debugfs_features',
                     'trace_features', 'all'],
            default=['all'], help='info to print')
    return parser
