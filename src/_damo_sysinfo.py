# SPDX-License-Identifier: GPL-2.0

'''
Contains code for managing system information including kernel version and
DAMON features enabled on the kernel.
'''

import collections
import json
import os
import subprocess

import _damon_dbgfs
import _damon_sysfs
import damo_version

class DamonFeature:
    name = None
    upstream_status = None
    upstreamed_version = None
    comments = None

    def __init__(self, name, upstream_status, upstreamed_version='unknown',
                 comments=''):
        self.name = name
        self.upstream_status = upstream_status
        self.upstreamed_version = upstreamed_version
        self.comments = comments

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('name', self.name),
            ('upstream_status', self.upstream_status),
            ('upstreamed_version', self.upstreamed_version),
            ('comments', self.comments),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        if 'upstreamed_version' in kvpairs:
            upstreamed_version = kvpairs['upstreamed_version']
        else:
            upstreamed_version = 'unknown'
        return cls(kvpairs['name'], kvpairs['upstream_status'],
                   upstreamed_version,
                   kvpairs['comments'])

    def __eq__(self, other):
        return self.name == other.name and \
                self.upstream_status == other.upstream_status and \
                self.upstreamed_version == other.upstreamed_version and \
                self.comments == other.comments

class SystemInfo:
    damo_version = None
    kernel_version = None

    # list of DamonFeature objects that can be used using sysfs and debugfs
    # interfaces.
    avail_damon_sysfs_features = None
    avail_damon_debugfs_features = None
    avail_damon_trace_features = None

    # list of DamonFeature objects that tested to generate
    # avail_damon_{sys,debug}fs_features.
    tested_features = None

    def __init__(self, damo_version, kernel_version,
                 avail_damon_sysfs_features, avail_damon_debugfs_features,
                 avail_damon_trace_features=[], tested_features=[]):
        self.damo_version = damo_version
        self.kernel_version = kernel_version
        self.avail_damon_sysfs_features = avail_damon_sysfs_features
        self.avail_damon_debugfs_features = avail_damon_debugfs_features
        self.avail_damon_trace_features = avail_damon_trace_features
        self.tested_features = tested_features

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('damo_version', self.damo_version),
            ('kernel_version', self.kernel_version),
            ('avail_damon_sysfs_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_sysfs_features]),
            ('avail_damon_debugfs_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_debugfs_features]),
            ('avail_damon_trace_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_trace_features]),
            ('tested_features',
             [f.to_kvpairs(raw) for f in self.tested_features]),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        damon_trace_features = []
        if 'avail_damon_trace_features' in kvpairs:
            damon_trace_features = kvpairs['avail_damon_trace_features']
        return cls(
                damo_version=kvpairs['damo_version'],
                kernel_version=kvpairs['kernel_version'],
                avail_damon_sysfs_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    kvpairs['avail_damon_sysfs_features']],
                avail_damon_debugfs_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    kvpairs['avail_damon_debugfs_features']],
                avail_damon_trace_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    damon_trace_features],
                tested_features=[
                    DamonFeature.from_kvpairs(kvp) for kvp in
                    kvpairs['tested_features']],
                )

    def __eq__(self, other):
        return self.damo_version == other.damo_version and \
                self.kernel_version == other.kernel_version and \
                self.avail_damon_sysfs_features == \
                other.avail_damon_sysfs_features and \
                self.avail_damon_debugfs_features == \
                other.avail_damon_debugfs_features and \
                self.avail_damon_trace_features == \
                other.avail_damon_trace_features and \
                self.tested_features == other.tested_features

damon_features = [
        DamonFeature(
            name='record', upstream_status='withdrawn',
            upstreamed_version='none',
            comments='was in DAMON patchset, but not merged in mainline'),
        DamonFeature(name='vaddr', upstream_status='merged in v5.15',
                     upstreamed_version='5.15'),
        DamonFeature(name='trace_damon_aggregated',
                      upstream_status='merged in v5.15 (2fcb93629ad8)',
                      upstreamed_version='5.15'),
        DamonFeature(name='schemes', upstream_status='merged in v5.16',
                     upstreamed_version='5.16'),
        DamonFeature(name='init_regions',
                     upstream_status='merged in v5.16 (90bebce9fcd6)',
                     upstreamed_version='5.16'),
        DamonFeature(name='paddr',
                     upstream_status='merged in v5.16 (a28397beb55b)',
                     upstreamed_version='5.16'),
        DamonFeature(name='schemes_speed_limit',
                     upstream_status='merged in v5.16 (2b8a248d5873)',
                     upstreamed_version='5.16'),
        DamonFeature(name='schemes_quotas',
                     upstream_status='merged in v5.16 (1cd243030059)',
                     upstreamed_version='5.16'),
        DamonFeature(name='schemes_prioritization',
                     upstream_status='merged in v5.16 (38683e003153)',
                     upstreamed_version='5.16'),
        DamonFeature(name='schemes_wmarks',
                     upstream_status='merged in v5.16 (ee801b7dd782)',
                     upstreamed_version='5.16'),
        DamonFeature(name='schemes_stat_succ',
                     upstream_status='merged in v5.17 (0e92c2ee9f45)',
                     upstreamed_version='5.17'),
        DamonFeature(name='schemes_stat_qt_exceed',
                     upstream_status='merged in v5.17 (0e92c2ee9f45)',
                     upstreamed_version='5.17'),
        DamonFeature(name='init_regions_target_idx',
                     upstream_status='merged in v5.18 (144760f8e0c3)',
                     upstreamed_version='5.18'),
        DamonFeature(name='fvaddr',
                     upstream_status='merged in v5.19 (b82434471cd2)',
                     upstreamed_version='5.19'),
        DamonFeature(name='schemes_tried_regions',
                     upstream_status='merged in v6.2-rc1',
                     upstreamed_version='6.2'),
        DamonFeature(name='schemes_filters',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='schemes_filters_anon',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='schemes_filters_memcg',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='schemes_tried_regions_sz',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),
        DamonFeature(name='schemes_filters_addr',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),
        DamonFeature(name='schemes_filters_target',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),
        DamonFeature(name='schemes_apply_interval',
                     upstream_status='merged in v6.7-rc1',
                     upstreamed_version='6.7'),
        DamonFeature(name='trace_damos_before_apply',
                     upstream_status='merged in v6.7-rc1 (c603c630b509)',
                     upstreamed_version='6.7'),
        DamonFeature(name='schemes_quota_goals',
                     upstream_status='merged in v6.8-rc1',
                     upstreamed_version='6.8'),
        DamonFeature(name='schemes_quota_effective_bytes',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='schemes_quota_goal_metric',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='schemes_quota_goal_some_psi',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='schemes_filters_young',
                     upstream_status='merged in v6.10-rc1',
                     upstreamed_version='6.10'),
        DamonFeature(name='schemes_migrate',
                     upstream_status='merged in v6.11-rc1',
                     upstreamed_version='6.11'),
        DamonFeature(name='sz_ops_filter_passed',
                     upstream_status='merged in v6.14-rc1',
                     upstreamed_version='6.14'),
        DamonFeature(name='allow_filter',
                     upstream_status='merged in v6.14-rc1',
                     upstreamed_version='6.14'),
        DamonFeature(name='schemes_filters_hugepage_size',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='schemes_filters_unmapped',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='intervals_goal',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='schemes_filters_core_ops_dirs',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='schemes_filters_active',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='schemes_quota_goal_node_mem_used_free',
                     upstream_status='merged in v6.16-rc1',
                     upstreamed_version='6.16'),
        DamonFeature(name='schemes_dests',
                     upstream_status='merged in v6.17-rc1',
                     upstreamed_version='6.17'),
        DamonFeature(name='sysfs_refresh_ms',
                     upstream_status='merged in v6.17-rc1',
                     upstreamed_version='6.17'),
        DamonFeature(name='trace_damon_monitor_intervals_tune',
                     upstream_status='merged in v6.17-rc1 (214db7028727)',
                     upstreamed_version='6.17'),
        DamonFeature(name='trace_damos_esz',
                     upstream_status='merged in v6.17-rc1 (a86d695193bf);',
                     upstreamed_version='6.17'),
        DamonFeature(name='addr_unit',
                     upstream_status='merged in v6.18-rc1',
                     upstreamed_version='6.18'),
        DamonFeature(name='schemes_quota_goal_node_memcg_used_free',
                     upstream_status='merged in mm, expectred for 6.19-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='obsolete_target',
                     upstream_status='merged in mm, expected for 6.19-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='ops_attrs',
                     upstream_status='hacking on damon/next',
                     upstreamed_version='none'),
        ]

system_info = None
sysinfo_file_path = os.path.join(os.environ['HOME'], '.damo.sysinfo')

def read_sysinfo():
    '''
    Read save_sysinfo()-saved SystemInfo object.
    Returns read SystemInfo object and an error string if failed.
    '''
    if not os.path.isfile(sysinfo_file_path):
        return None, 'sysinfo file (%s) not found' % sysinfo_file_path
    try:
        with open(sysinfo_file_path, 'r') as f:
            kvpairs = json.load(f)
    except Exception as e:
        return None, 'json load of %s failed' % sysinfo_file_path
    return SystemInfo.from_kvpairs(kvpairs), None

def valid_cached_sysinfo(sysinfo, damo_version_, kernel_version):
    if sysinfo.damo_version != damo_version_:
        return False
    if sysinfo.kernel_version != kernel_version:
        return False
    return sysinfo.tested_features == damon_features

def set_sysinfo_from_cache():
    sysinfo, err = read_sysinfo()
    if err is not None:
        return 'reading saved sysinfo fail (%s)' % err
    damo_version_ = damo_version.__version__
    kernel_version = subprocess.check_output(['uname', '-r']).decode().strip()
    if not valid_cached_sysinfo(sysinfo, damo_version_, kernel_version):
        return 'cached sysinfo cannot be used'
    global system_info
    system_info = sysinfo
    return None

def avail_features_on(damon_fs):
    if not damon_fs.supported():
        return [], None
    feature_supports_map, err = damon_fs.mk_feature_supports_map()
    if err is not None:
        return None, 'feature map making fail (%s)' % err
    avail_features = [f for f in damon_features if feature_supports_map[f.name]]
    return avail_features, None

def get_damon_tracepoints():
    '''
    returns list of DAMON tracepoint names and an error
    '''
    try:
        perf_output = subprocess.check_output(
                ['perf', 'list', 'tracepoint']).decode().strip()
    except Exception as e:
        return None, 'perf list fail (%s)' % e
    points = []
    for line in perf_output.split('\n'):
        fields = line.split()
        if fields[0].startswith('damon:'):
            points.append(fields[0])
    return points, None

def damon_feature_of_name(name):
    return [f for f in damon_features if f.name == name][0]

def get_avail_damon_trace_features():
    features = []
    tracepoints, err = get_damon_tracepoints()
    if err is not None:
        return None, err
    tracepoint_to_feature_name_map = {
            'damon:damon_aggregated': 'trace_damon_aggregated',
            'damon:damos_before_apply': 'trace_damos_before_apply',
            'damon:damon_monitor_intervals_tune':
            'trace_damon_monitor_intervals_tune',
            'damon:damos_esz': 'trace_damos_esz',
            }
    for tracepoint, feature_name in tracepoint_to_feature_name_map.items():
        if tracepoint in tracepoints:
            features.append(damon_feature_of_name(feature_name))
    return features, err

def set_sysinfo_from_scratch():
    damo_version_ = damo_version.__version__
    kernel_version = subprocess.check_output(['uname', '-r']).decode().strip()
    avail_damon_sysfs_features, err = avail_features_on(_damon_sysfs)
    if err is not None:
        return 'sysfs feature check fail (%s)' % err
    avail_damon_debugfs_features, err = avail_features_on(_damon_dbgfs)
    if err is not None:
        return 'debugfs feature check fail (%s)' % err
    avail_damon_trace_features, err = get_avail_damon_trace_features()
    if err is not None:
        return 'trace feature check fail (%s)' % err

    tested_features = [f for f in damon_features]
    sysinfo = SystemInfo(
            damo_version=damo_version_,
            kernel_version=kernel_version,
            avail_damon_sysfs_features=avail_damon_sysfs_features,
            avail_damon_debugfs_features=avail_damon_debugfs_features,
            avail_damon_trace_features=avail_damon_trace_features,
            tested_features=tested_features)
    global system_info
    system_info = sysinfo
    return None

def set_sysinfo():
    '''
    Set system_info global variable.

    Returns an error if failed.
    '''
    err = set_sysinfo_from_cache()
    if err is None:
        return None
    err = set_sysinfo_from_scratch()
    if err is None:
        save_sysinfo()
        return None
    return 'system info setup fail (%s)' % err

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

def rm_sysinfo_file():
    try:
        os.remove(sysinfo_file_path)
    except Exception as e:
        return '%s' % e
    return None

def get_sysinfo():
    if system_info is None:
        err = set_sysinfo()
        if err is not None:
            return None, err
    return system_info, None
