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
    print('damo version: %s' % sysinfo.damo_version)
    print('kernel version: %s' % sysinfo.kernel_version)
    print('Sysfs avail DAMON features')
    for feature in sysinfo.avail_damon_sysfs_features:
        pr_feature(feature)
    print('Debugfs avail DAMON features')
    for feature in sysinfo.avail_damon_debugfs_features:
        pr_feature(feature)
    print('DAMON trace features')
    for feature in sysinfo.avail_damon_trace_features:
        pr_feature(feature)

def set_argparser(parser):
    return parser
