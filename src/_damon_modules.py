# SPDX-License-Identifier: GPL-2.0

'''
Contains core functions for DAMON modules.
'''

import os
import subprocess

import _damo_fs
import _damo_sysinfo
import _damon
import damo_pa_layout

def damon_stat_available():
    param_dir = '/sys/module/damon_stat/parameters'
    if not os.path.isdir(param_dir):
        return False
    with open(os.path.join(param_dir, 'enabled'), 'r') as f:
        if f.read().strip() != 'Y':
            return False
    # TODO: use stat/aggr_interval damon feature
    return os.path.isfile(os.path.join(param_dir, 'aggr_interval_us'))

def damon_stat_kdamonds():
    param_dir = '/sys/module/damon_stat/parameters'
    if not os.path.isdir(param_dir):
        return None, 'param dir (%s) not found' % param_dir
    with open(os.path.join(param_dir, 'enabled'), 'r') as f:
        if f.read().strip() != 'Y':
            return None, 'not running'
    try:
        kdamond_pid = subprocess.check_output(
                ['pidof', 'kdamond.0']).decode().strip()
    except Exception as e:
        return None, 'pidof kdamond.0 fail (%s)' % e
    intervals = _damon.DamonIntervals()
    intervals.intervals_goal = _damon.DamonIntervalsGoal(
            access_bp=400, aggrs=3, min_sample_us=5000, max_sample_us=10000000)
    target_regions = [
            _damon.DamonRegion(r[0], r[1])
            for r in [damo_pa_layout.default_paddr_region()]]
    target = _damon.DamonTarget(
            pid=None, regions=target_regions)
    context = _damon.DamonCtx(intervals=intervals, targets=[target])
    kdamond = _damon.Kdamond(state='on', pid=kdamond_pid, contexts=[context])
    kdamond.interface = 'damon_stat'
    return [kdamond], None


def damon_stat_running():
    enabled_file = '/sys/module/damon_stat/parameters/enabled'
    try:
        with open(enabled_file, 'r') as f:
            return f.read().strip() == 'Y'
    except:
        return False

def damon_stat_avail():
    param_dir = '/sys/module/damon_stat/parameters/'
    aggr_interval_us_file = os.path.join(param_dir, 'aggr_interval_us')
    if not os.path.isfile(aggr_interval_us_file):
        return False
    enabled_file = os.path.join(param_dir, 'enabled')
    with open(enabled_file, 'r') as f:
        if f.read().strip().lower() == 'n':
            return False
    return True

def read_damon_stat_param(param_name):
    file_path = os.path.join('/sys/module/damon_stat/parameters', param_name)
    with open(file_path, 'r') as f:
        return f.read().strip()

def get_avail_features():
    features = []
    sysfs_path = _damo_fs.dev_mount_point('sysfs')
    if sysfs_path is None:
        return features

    mod_path = os.path.join(sysfs_path, 'module')
    if os.path.isfile(os.path.join(mod_path, 'damon_stat', 'parameters',
                                   'aggr_interval_us')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('stat/aggr_interval'))
        features.append(
                _damo_sysinfo.damon_feature_of_name('stat/negative_idle_time'))
    return features

def get_avail_interface_features():
    features = []
    sysfs_path = _damo_fs.dev_mount_point('sysfs')
    if sysfs_path is None:
        return features

    mod_path = os.path.join(sysfs_path, 'module')
    if not os.path.isdir(mod_path):
        return features
    if os.path.isdir(os.path.join(mod_path, 'damon_reclaim')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('interface/damon_reclaim'))
    if os.path.isdir(os.path.join(mod_path, 'damon_lru_sort')):
        features.append(
                _damo_sysinfo.damon_feature_of_name(
                    'interface/damon_lru_sort'))
    if os.path.isdir(os.path.join(mod_path, 'damon_stat')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('interface/damon_stat'))
    return features
