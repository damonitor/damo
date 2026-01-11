# SPDX-License-Identifier: GPL-2.0

'''
Contains code for managing system information including kernel version and
DAMON features enabled on the kernel.
'''

import collections
import json
import os
import subprocess

import _damo_fs
import _damo_subproc
import _damon_dbgfs
import _damon_features
import _damon_sysfs
import damo_version

class SystemInfo:
    damo_version = None
    kernel_version = None

    sysfs_path = None
    tracefs_path = None
    debugfs_path = None

    trace_cmd_version = None
    perf_path = None
    perf_version = None

    # DAMON features that available on current kernel.
    avail_damon_features = None

    def __init__(self, damo_version, kernel_version,
                 perf_path=None, perf_version=None, trace_cmd_version=None,
                 sysfs_path=None, tracefs_path=None, debugfs_path=None,
                 avail_damon_features=None):
        self.damo_version = damo_version
        self.kernel_version = kernel_version

        self.sysfs_path = sysfs_path
        self.tracefs_path = tracefs_path
        self.debugfs_path = debugfs_path

        self.trace_cmd_version=trace_cmd_version
        self.perf_path = perf_path
        self.perf_version = perf_version

        self.avail_damon_features = avail_damon_features

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('damo_version', self.damo_version),
            ('kernel_version', self.kernel_version),
            ('sysfs_path', self.sysfs_path),
            ('tracefs_path', self.tracefs_path),
            ('debugfs_path', self.debugfs_path),
            ('trace_cmd_version', self.trace_cmd_version),
            ('perf_path', self.perf_path),
            ('perf_version', self.perf_version),
            ('avail_damon_features',
             [f.to_kvpairs(raw) for f in self.avail_damon_features]),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        trace_cmd_version = None
        if 'trace_cmd_version' in kvpairs:
            trace_cmd_version = kvpairs['trace_cmd_version']
        perf_path = None
        if 'perf_path' in kvpairs:
            perf_path = kvpairs['perf_path']
        perf_version = None
        if 'perf_version' in kvpairs:
            perf_version = kvpairs['perf_version']
        avail_damon_features = []
        if 'avail_damon_features' in kvpairs:
            avail_damon_features = kvpairs['avail_damon_features']
        damon_modules = []
        sysfs_path = None
        if 'sysfs_path' in kvpairs:
            sysfs_path = kvpairs['sysfs_path']
        tracefs_path = None
        if 'tracefs_path' in kvpairs:
            tracefs_path = kvpairs['tracefs_path']
        debugfs_path = None
        if 'debugfs_path' in kvpairs:
            debugfs_path = kvpairs['debugfs_path']
        return cls(
                damo_version=kvpairs['damo_version'],
                kernel_version=kvpairs['kernel_version'],
                sysfs_path=sysfs_path,
                tracefs_path=tracefs_path,
                debugfs_path=debugfs_path,
                trace_cmd_version=trace_cmd_version,
                perf_path=perf_path, perf_version=perf_version,
                avail_damon_features=[
                    _damon_features.DamonFeature.from_kvpairs(kvp) for kvp in
                    avail_damon_features],
                )

    def __eq__(self, other):
        return self.damo_version == other.damo_version and \
                self.kernel_version == other.kernel_version and \
                self.sysfs_path == other.sysfs_path and \
                self.tracefs_path == other.tracefs_path and \
                self.debugfs_path == other.debugfs_path and \
                self.trace_cmd_version == other.trace_cmd_version and \
                self.perf_path == other.perf_path and \
                self.perf_version == other.perf_version and \
                self.avail_damon_features == other.avail_damon_features

    def feature_available(self, feature_name):
        return feature_name in [f.name for f in self.avail_damon_features]

    def infer_damon_version(self):
        '''Return version string and error'''
        avail_features = {f.name for f in self.avail_damon_features}
        if len(avail_features) == 0:
            return '<5.15', None
        for feature in reversed(_damon_features.features_list):
            if feature.name in avail_features:
                if feature.upstreamed_version in ['none', 'unknown']:
                    append_plus = True
                else:
                    version = feature.upstreamed_version
                    if append_plus:
                        version = '%s+' % version
                    return version, None
        return None, 'only non-upstreamed features'

system_info = None
sysinfo_file_path = os.path.join(os.environ['HOME'], '.damo.sysinfo')

def read_sysinfo_file():
    '''
    Read save_sysinfo_file()-saved SystemInfo object.
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
    return True

def set_sysinfo_from_cache():
    sysinfo, err = read_sysinfo_file()
    if err is not None:
        return 'reading saved sysinfo fail (%s)' % err
    damo_version_ = damo_version.get_real_version()
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
    avail_features = [f for f in _damon_features.features_list
                      if feature_supports_map[f.name]]
    return avail_features, None

def get_damon_tracepoints():
    '''
    returns list of DAMON tracepoint names and an error
    '''
    tracefs_path = _damo_fs.dev_mount_point('tracefs')
    if tracefs_path is None:
        return None, 'tracefs is not mounted'
    points = []
    try:
        with open(os.path.join(tracefs_path, 'available_events'), 'r') as f:
            for line in f:
                if line.startswith('damon:'):
                    points.append(line.strip())
    except Exception as e:
        return None, 'available tracepoints reading fail'
    return points, None

def damon_feature_of_name(name):
    return [f for f in _damon_features.features_list if f.name == name][0]

tracepoint_to_feature_name_map = {
        'damon:damon_aggregated': 'trace/damon_aggregated',
        'damon:damos_before_apply': 'trace/damos_before_apply',
        'damon:damon_monitor_intervals_tune':
        'trace/damon_monitor_intervals_tune',
        'damon:damos_esz': 'trace/damos_esz',
        'damon:damos_stat_after_apply_interval':
        'trace/damos_stat_after_apply_interval',
        }

def get_avail_damon_trace_features():
    features = []
    tracepoints, err = get_damon_tracepoints()
    if err is not None:
        return None, err
    for tracepoint, feature_name in tracepoint_to_feature_name_map.items():
        if tracepoint in tracepoints:
            features.append(damon_feature_of_name(feature_name))
    return features, err

def get_avail_damon_modules():
    features = []

    if _damon_dbgfs.supported():
        features.append(damon_feature_of_name('module/damon_debugfs'))

    sysfs_path = _damo_fs.dev_mount_point('sysfs')
    if sysfs_path is None:
        return features

    if _damon_sysfs.supported():
        features.append(damon_feature_of_name('module/damon_sysfs'))

    mod_path = os.path.join(sysfs_path, 'module')
    if not os.path.isdir(mod_path):
        return features
    if os.path.isdir(os.path.join(mod_path, 'damon_reclaim')):
        features.append(damon_feature_of_name('module/damon_reclaim'))
    if os.path.isdir(os.path.join(mod_path, 'damon_lru_sort')):
        features.append(damon_feature_of_name('module/damon_lru_sort'))
    if os.path.isdir(os.path.join(mod_path, 'damon_stat')):
        features.append(damon_feature_of_name('module/damon_stat'))
    return features

def get_trace_cmd_version():
    if not _damo_subproc.avail_cmd('trace-cmd'):
        return None
    try:
        output = subprocess.check_output(['trace-cmd']).decode().strip()
    except Exception as e:
        output = e.output.decode().strip()
    for line in output.split('\n'):
        # version line is, e.g., trace-cmd version 3.3.1 (not-a-git-repo)
        if not line.startswith('trace-cmd version '):
            continue
        fields = line.split()
        return ' '.join(fields[2:])
    return None

def get_perf_path_version():
    try:
        perf_path = subprocess.check_output(['which', 'perf']).decode().strip()
    except:
        perf_path = None
    if perf_path is not None:
        perf_version = subprocess.check_output(
                ['perf', '--version']).decode().strip()
    else:
        perf_version = None
    return perf_path, perf_version

def get_sysinfo_from_scratch():
    damo_version_ = damo_version.get_real_version()
    kernel_version = subprocess.check_output(['uname', '-r']).decode().strip()
    sysfs_path = _damo_fs.dev_mount_point('sysfs')
    tracefs_path = _damo_fs.dev_mount_point('tracefs')
    debugfs_path = _damo_fs.dev_mount_point('debugfs')

    trace_cmd_version = get_trace_cmd_version()
    perf_path, perf_version = get_perf_path_version()

    avail_damon_features = []
    avail_damon_sysfs_features, err = avail_features_on(_damon_sysfs)
    if err is not None:
        return None, 'sysfs feature check fail (%s)' % err
    avail_damon_features += avail_damon_sysfs_features

    avail_damon_debugfs_features, err = avail_features_on(_damon_dbgfs)
    if err is not None:
        return None, 'debugfs feature check fail (%s)' % err
    avail_damon_features += avail_damon_debugfs_features

    avail_damon_trace_features, err = get_avail_damon_trace_features()
    if err is not None:
        return None, 'trace feature check fail (%s)' % err
    avail_damon_features += avail_damon_trace_features

    avail_damon_modules = get_avail_damon_modules()
    avail_damon_features += avail_damon_modules

    sysinfo = SystemInfo(
            damo_version=damo_version_,
            kernel_version=kernel_version,
            sysfs_path=sysfs_path,
            tracefs_path=tracefs_path,
            debugfs_path=debugfs_path,
            trace_cmd_version=trace_cmd_version,
            perf_path=perf_path, perf_version=perf_version,
            avail_damon_features=avail_damon_features)
    return sysinfo, None

def version_mismatch(sysinfo):
    if sysinfo.damo_version != damo_version.get_real_version():
        return True
    kernel_version = subprocess.check_output(['uname', '-r']).decode().strip()
    if sysinfo.kernel_version != kernel_version:
        return True
    return False

def update_cached_info(cached_info):
    if cached_info is None:
        return get_sysinfo_from_scratch()
    if version_mismatch(cached_info):
        return get_sysinfo_from_scratch()

    trace_cmd_version = get_trace_cmd_version()
    perf_path, perf_version = get_perf_path_version()

    sysfs_path = _damo_fs.dev_mount_point('sysfs')
    if cached_info.sysfs_path != sysfs_path:
        cached_info.sysfs_path = sysfs_path
        avail_damon_sysfs_features, err = avail_features_on(_damon_sysfs)
        if err is not None:
            return None, 'damon sysfs features update fail (%s)' % err

        avail_damon_modules = get_avail_damon_modules()

        avail_damon_features = []
        for f in cached_info.avail_damon_features:
            if f.name.startswith('sysfs/') or f.name.startswith('module/'):
                continue
            avail_damon_features.append(f)
        avail_damon_features += avail_damon_sysfs_feastures
        avail_damon_features += avail_damon_modules
        cached_info.avail_damon_features = avail_damon_features

    tracefs_path = _damo_fs.dev_mount_point('tracefs')
    if cached_info.tracefs_path != tracefs_path:
        cached_info.tracefs_path = tracefs_path
        avail_damon_trace_features, err = get_avail_damon_trace_features()
        if err is not None:
            return None, 'damon trace features update fail (%s)' % err

        avail_damon_features = []
        for f in cached_info.avail_damon_features:
            if f.name.startswith('trace/'):
                continue
            avail_damon_features.append(f)
        avail_damon_features += avail_damon_trace_features
        cached_info.avail_damon_features = avail_damon_features

    debugfs_path = _damo_fs.dev_mount_point('debugfs')
    if cached_info.debugfs_path != debugfs_path:
        cached_info.debugfs_path = debugfs_path
        avail_damon_debugfs_features, err = avail_features_on(_damon_debugfs)
        if err is not None:
            return None, 'damon debugfs features update fail (%s)' % err

        avail_damon_features = []
        for f in cached_info.avail_damon_features:
            if f.name.startswith('debugfs/'):
                continue
            avail_damon_features.append(f)
        avail_damon_features += avail_damon_debugfs_features
        cached_info.avail_damon_features = avail_damon_features

    return cached_info, None

def load_sysinfo():
    '''
    Set system_info global variable.

    Returns an error if failed.
    '''
    cached_info, cache_read_err = read_sysinfo_file()
    info, err = update_cached_info(cached_info)
    if err is not None:
        errs = []
        if cache_read_err is not None:
            errs.append('cache read fail (%s)' % cache_read_err)
        errs.append('info update fail (%s)' % err)
        return 'sysinfo loading fail (%s)' % ', '.join(errs)

    global system_info
    system_info = info
    save_sysinfo_file()
    return None

def save_sysinfo_file():
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
        err = load_sysinfo()
        if err is not None:
            return None, err
    return system_info, None

def damon_tracepoint_available(tracepoint):
    sysinfo, err = get_sysinfo()
    if err is not None:
        return False
    feature_name = tracepoint_to_feature_name_map[tracepoint]
    return feature_name in [f.name for f in sysinfo.avail_damon_features]

def damon_feature_available(feature_name):
    sysinfo, err = get_sysinfo()
    if err is not None:
        return False
    for f in sysinfo.avail_damon_features:
        if f.name == feature_name:
            return True
    return False
