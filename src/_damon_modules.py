# SPDX-License-Identifier: GPL-2.0

'''
Contains core functions for DAMON modules.

Note that this is not for sample modules.
'''

import os
import subprocess

import _damo_fs
import _damo_sysinfo
import _damon
import damo_pa_layout

def get_param_dir(module_name):
    sysinfo, err = get_sysinfo()
    if err is not None:
        # what can we do other than panic?
        print('[PANIC] get_sysinfo() fail (%s)' % err)
        exit(1)
    return os.path.join(sysinfo.sysfs_path, 'module', module_name,
                        'parameters')

def get_param_file(module_name, parameter):
    return os.path.join(get_param_dir(module), parameter)

def damon_stat_running():
    enabled_file = get_param_file('damon_stat', 'enabled')
    # this function could be called without damon_stat availability.
    # catch open error for the case.
    try:
        with open(enabled_file, 'r') as f:
            return f.read().strip() == 'Y'
    except:
        return False

def damon_stat_kdamonds():
    param_dir = get_param_dir('damon_stat')
    if not os.path.isdir(param_dir):
        return None, 'param dir (%s) not found' % param_dir
    if not damon_stat_running():
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

def read_damon_stat_param(param_name):
    file_path = get_param_file('damon_stat', param_name)
    with open(file_path, 'r') as f:
        return f.read().strip()

def get_avail_features():
    features = []
    # this is called while sysinfo setup, so cannot use sysinfo.sysfs_path
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
    if os.path.isfile(os.path.join(mod_path, 'damon_lru_sort', 'parameters',
                                   'addr_unit')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('lru_sort/addr_unit'))

    if os.path.isfile(os.path.join(mod_path, 'damon_lru_sort', 'parameters',
                                   'autotune_monitoring_intervals')):
        for name in ['lru_sort/young_page_filter', 'lru_sort/active_mem_bp',
                     'lru_sort/autotune_monitoring_intervals']:
            features.append(
                    _damo_sysinfo.damon_feature_of_name(name))

    reclaim_dir = os.path.join(mod_path, 'damon_reclaim', 'parameters')
    if os.path.isfile(os.path.join(reclaim_dir, 'nr_quota_exceeds')):
        features.append(_damo_sysinfo.damon_feature_of_name('reclaim/stats'))
    if os.path.isfile(os.path.join(reclaim_dir, 'commit_inputs')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('reclaim/commit_inputs'))
    if os.path.isfile(os.path.join(reclaim_dir, 'skip_anon')):
        features.append(
                _damo_sysinfo.damon_feature_of_name('reclaim/skip_anon'))
    if os.path.isfile(os.path.join(mod_path, 'damon_reclaim', 'parameters',
                                   'addr_unit')):
        features.append(_damo_sysinfo.damon_feature_of_name(
            'reclaim/addr_unit'))

    return features

def get_avail_interface_features():
    features = []
    # this is called while sysinfo setup, so cannot use sysinfo.sysfs_path
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
