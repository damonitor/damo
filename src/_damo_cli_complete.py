# SPDX-License-Identifier: GPL-2.0

import datetime
import os
import sys

def log(msg):
    msg = '%s: %s' % (datetime.datetime.now(), msg)
    with open('.damo_cli_complete_log', 'a') as f:
        f.write('%s\n' % msg)

def damon_param_candidates(words, cword):
    if cword == 0 or words[cword].startswith('-'):
        return ['--monitoring_intervals_autotune', '--damos_action']
    return []

def start_candidates(words, cword):
    return damon_param_candidates(words[2:], cword - 2)

def tune_candidates(words, cword):
    return damon_param_candidates(words[2:], cword - 2)

def record_candidates(words, cword):
    if cword == 2 or words[cword].startswith('-'):
        return ['--out', '--help', '--snapshot', '--timeout',
                '--snapshot_damos_filter']
    return []

def report_access_candidates(words, cword):
    if cword == 3 or words[cword].startswith('-'):
        return ['--input', '--snapshot_damos_filter', '--style']
    # cword is larger than 3.
    prev = words[cword - 1]
    if prev == '--input':
        candidates = ['tried_regions_of', './', '../']
        for f in os.listdir('./'):
            candidates.append('./%s' % f)
        return candidates
    if prev == '--style':
        return ['detailed', 'simple-boxes', 'temperature-sz-hist',
                'recency-sz-hist', 'cold-memory-tail', 'recency-percentiles',
                'idle-time-percentiles', 'temperature-percentiles', 'cold',
                'hot']
    return []

def report_damon_candidates(words, cword):
    if cword == 3 or words[cword].startswith('-'):
        return ['--format', '--show_cpu_usage', '--kdamonds_summary',
                '--damos_stats']
    return []

def report_sysinfo_candidates(words, cword):
    if cword == 3 or words[cword].startswith('-'):
        return ['--print', '--invalidate_cache']
    for idx in range(cword, 2, -1):
        if words[idx] == '--print':
            return ['versions', 'fs_info', 'trace_cmd_info', 'perf_info',
                    'sysfs_features', 'debugfs_features', 'trace_features',
                    'modules', 'all']
    return []

def report_candidates(words, cword):
    if cword == 2:
        return ['access', 'damon holistic', 'heatmap', 'sysinfo']
    report_type = words[2]
    if report_type == 'access':
        return report_access_candidates(words, cword)
    if report_type == 'damon':
        return report_damon_candidates(words, cword)
    if report_type == 'sysinfo':
        return report_sysinfo_candidates(words, cword)
    return []

def help_candidtes(words, cword):
    if cword == 2:
        return ['damon_param_options', 'access_filter_options',
                'access_format_options']
    if cword == 3:
        topic = words[2]
        if topic == 'damon_param_options':
            return ['all', 'monitoring', 'damos']
        if topic == 'access_format_options':
            return ['options', 'record_format_keywords',
                    'snapshot_format_keywords', 'region_format_keywords']
    return []

def handle_cli_complete():
    '''
    Print command line auto-completion suggestions.  Read
    scripts/damo-completion.sh and src/damo.py to see how this is called.

    Note that this is not supporting full options.  Only commands and options
    that expected to be frequently used are supported.
    '''
    if len(sys.argv) < 4:
        return False
    if sys.argv[1] != '--cli_complete':
        return False
    cword = int(sys.argv[2])
    words = sys.argv[3:]
    if cword == 0:
        return True
    candidates = []
    if cword == 1:
        candidates = ['start', 'stop', 'tune', 'record', 'report', 'help',
                      'version']
    cmd = words[1]
    if cmd == 'start':
        candidates = start_candidates(words, cword)
    elif cmd == 'tune':
        candidates = tune_candidates(words, cword)
    elif cmd == 'record':
        candidates = record_candidates(words, cword)
    elif cmd == 'report':
        candidates = report_candidates(words, cword)
    elif cmd == 'help':
        candidates = help_candidtes(words, cword)
    if words[cword - 1] != '--help':
        candidates.append('--help')
    print(' '.join(candidates))
    return True
