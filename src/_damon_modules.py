# SPDX-License-Identifier: GPL-2.0

'''
Contains core functions for DAMON modules.
'''

import os
import subprocess

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
