# SPDX-License-Identifier: GPL-2.0

'''
Contains code for managing system information including kernel version and
DAMON features enabled on the kernel.
'''

import collections
import json
import os

class DamonFeature:
    name = None
    upstream_status = None
    comments = None

    def __init__(self, name, upstream_status, comments=''):
        self.name = name
        self.upstream_status = upstream_status
        self.comments = comments

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('name', self.name),
            ('upstream_status', self.upstream_status),
            ('comments', self.comments),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        return cls(kvpairs['name'], kvpairs['upstream_status'],
                   kvpairs['comments'])

    def __eq__(self, other):
        return self.name == other.name and \
                self.upstream_status == other.upstream_status and \
                self.comments == other.comments

class SystemInfo:
    damo_version = None
    kernel_version = None

    # list of DamonFeature objects that can be used using sysfs and debugfs
    # interfaces.
    avail_damon_sysfs_features = None
    avail_damon_debugfs_features = None

    def __init__(self, damo_version, kernel_version,
                 avail_damon_sysfs_features, avail_damon_debugfs_features):
        self.damo_version = damo_version
        self.kernel_version = kernel_version
        self.avail_damon_sysfs_features = avail_damon_sysfs_features
        self.avail_damon_debugfs_features = avail_damon_debugfs_features

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('damo_version', self.damo_version),
            ('kernel_version', self.kernel_version),
            ('avail_damon_sysfs_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_sysfs_features]),
            ('avail_damon_debugfs_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_debugfs_features]),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        return cls(
                damo_version=kvpairs['damo_version'],
                kernel_version=kvpairs['kernel_version'],
                avail_damon_sysfs_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    kvpairs['avail_damon_sysfs_features']],
                avail_damon_debugfs_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    kvpairs['avail_damon_debugfs_features']]
                )

    def __eq__(self, other):
        return self.damo_version == other.damo_version and \
                self.kernel_version == other.kernel_version and \
                self.avail_damon_sysfs_features == \
                other.avail_damon_sysfs_features and \
                self.avail_damon_debugfs_features == \
                other.avail_damon_debugfs_features

damon_features = [
        DamonFeature(
            name='record', upstream_status='withdrawn',
            comments='was in DAMON patchset, but not merged in mainline'),
        DamonFeature(name='vaddr', upstream_status='merged in v5.15'),
        DamonFeature(name='schemes', upstream_status='merged in v5.16'),
        DamonFeature(name='init_regions',upstream_status='merged in v5.16 (90bebce9fcd6)'),
        DamonFeature(name='paddr', upstream_status='merged in v5.16 (a28397beb55b)'),
        DamonFeature(name='schemes_speed_limit', upstream_status='merged in v5.16 (2b8a248d5873)'),
        DamonFeature(name='schemes_quotas', upstream_status='merged in v5.16 (1cd243030059)'),
        DamonFeature(name='schemes_prioritization', upstream_status='merged in v5.16 (38683e003153)'),
        DamonFeature(name='schemes_wmarks', upstream_status='merged in v5.16 (ee801b7dd782)'),
        DamonFeature(name='schemes_stat_succ', upstream_status='merged in v5.17 (0e92c2ee9f45)'),
        DamonFeature(name='schemes_stat_qt_exceed', upstream_status='merged in v5.17 (0e92c2ee9f45)'),
        DamonFeature(name='init_regions_target_idx', upstream_status='merged in v5.18 (144760f8e0c3)'),
        DamonFeature(name='fvaddr', upstream_status='merged in v5.19 (b82434471cd2)'),
        DamonFeature(name='schemes_tried_regions', upstream_status='merged in v6.2-rc1'),
        DamonFeature(name='schemes_filters', upstream_status='merged in v6.3-rc1'),
        DamonFeature(name='schemes_filters_anon', upstream_status='merged in v6.3-rc1'),
        DamonFeature(name='schemes_filters_memcg', upstream_status='merged in v6.3-rc1'),
        DamonFeature(name='schemes_tried_regions_sz', upstream_status='merged in v6.6-rc1'),
        DamonFeature(name='schemes_filters_addr', upstream_status='merged in v6.6-rc1'),
        DamonFeature(name='schemes_filters_target', upstream_status='merged in v6.6-rc1'),
        DamonFeature(name='schemes_apply_interval', upstream_status='merged in v6.7-rc1'),
        DamonFeature(name='schemes_quota_goals', upstream_status='merged in v6.8-rc1'),
        DamonFeature(name='schemes_quota_effective_bytes', upstream_status='merged in v6.9-rc1'),
        DamonFeature(name='schemes_quota_goal_metric', upstream_status='merged in v6.9-rc1'),
        DamonFeature(name='schemes_quota_goal_some_psi', upstream_status='merged in v6.9-rc1'),
        DamonFeature(name='schemes_filters_young', upstream_status='merged in v6.10-rc1'),
        DamonFeature(name='schemes_migrate', upstream_status='merged in v6.11-rc1'),
        DamonFeature(name='sz_ops_filter_passed', upstream_status='merged in v6.14-rc1'),
        DamonFeature(name='allow_filter', upstream_status='merged in v6.14-rc1'),
        DamonFeature(name='schemes_filters_hugepage_size', upstream_status='merged in v6.15-rc1'),
        DamonFeature(name='schemes_filters_unmapped', upstream_status='merged in v6.15-rc1'),
        DamonFeature(name='intervals_goal', upstream_status='merged in v6.15-rc1'),
        DamonFeature(name='schemes_filters_core_ops_dirs', upstream_status='merged in v6.15-rc1'),
        DamonFeature(name='schemes_filters_active', upstream_status='merged in v6.15-rc1'),
        DamonFeature(name='schemes_quota_goal_node_mem_used_free', upstream_status='merged in v6.16-rc1'),
        DamonFeature(name='schemes_dests', upstream_status='merged in v6.17-rc1'),
        DamonFeature(name='sysfs_refresh_ms', upstream_status='merged in v6.17-rc1'),
        DamonFeature(name='addr_unit', upstream_status='merged in v6.18-rc1'),
        DamonFeature(name='schemes_quota_goal_node_memcg_used_free', upstream_status='merged in mm, expectred for 6.19-rc1'),
        DamonFeature(name='obsolete_target', upstream_status='merged in mm, expected for 6.19-rc1'),
        DamonFeature(name='ops_attrs', upstream_status='hacking on damon/next'),
        ]

system_info = None
sysinfo_file_path = os.path.join(os.environ['HOME'], '.damo.sysinfo')

def read_sysinfo():
    '''
    Setup system_info as a valid SystemInfo object.
    '''
    pass

def save_sysinfo():
    '''
    Save system_info as a file that we can read later.

    Returns error in case of failure.
    '''
    if system_info is None:
        return 'system_info is not initialized'
    try:
        with open(sysinfo_file_path, 'w') as f:
            json.dump(system_info.to_kvpairs(), f, indent=4)
    except Exception as e:
        return 'json dump fail (%s)' % e
    return None
