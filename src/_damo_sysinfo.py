# SPDX-License-Identifier: GPL-2.0

'''
Contains code for managing system information including kernel version and
DAMON features enabled on the kernel.
'''

class DamonFeature:
    name = None
    upstream_status = None
    comments = None

    def __init__(self, name, upstream_status, comments=''):
        self.name = name
        self.upstream_status = upstream_status
        self.comments = comments

class SystemInfo:
    damo_version = None
    kernel_version = None
    avail_damon_debugfs_features = None
    avail_damon_sysfs_features = None
