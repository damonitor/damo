# SPDX-License-Identifier: GPL-2.0

import datetime
import os
import sys

import _damon

def log(msg):
    msg = '%s: %s' % (datetime.datetime.now(), msg)
    with open('.damo_cli_complete_log', 'a') as f:
        f.write('%s\n' % msg)

class Option:
    name = None
    nr_args = None  # -1 for variable number of arguments

    def __init__(self, name, nr_args):
        self.name = name
        self.nr_args = nr_args

def prev_option_nr_filed_args(words, cword):
    for i in range(cword -1, -1, -1):
        if words[i].startswith('-'):
            prev_option = words[i]
            nr_filled_args = cword - 1 - i
            return prev_option, nr_filled_args
    return None, None

def can_suggest_options(words, cword, options):
    if cword == 0 or words[cword].startswith('-'):
        return True
    prev_option, nr_filled_args = prev_option_nr_filed_args(words, cword)
    if prev_option is None:
        return False
    for option in options:
        if option.name == prev_option and option.nr_args == nr_filled_args:
            return True
    return False

def get_candidates(words, cword, options):
    '''
    words and cword should start from the options part (no command).
    options should be a list of Option objects.
    '''
    if can_suggest_options(words, cword, options):
        return [o.name for o in options]
    return []

def should_show_options(words, cword, option_nr_args):
    '''
    words and cword should start from the options part (no command)
    option_nr_args is option name to their required number of arguments map.
    For variable number of options, -1 is given.
    '''
    if cword == 0 or words[cword].startswith('-'):
        return True

    prev_option, nr_filled_args = prev_option_nr_filed_args(words, cword)
    if prev_option is None:
        return False
    if not prev_option in option_nr_args:
        return False
    return option_nr_args[prev_option] == nr_filled_args

def option_candidates(words, cword, option_nr_args):
    '''
    words and cword should start from the options part (no command)
    option_nr_args is option name to their required number of arguments map.
    For variable number of options, -1 is given.
    '''
    if should_show_options(words, cword, option_nr_args):
        return list(option_nr_args.keys())
    return []

def damos_quota_goal_candidates(words, cword):
    prev_option, nr_filled_args = prev_option_nr_filed_args(words, cword)
    if prev_option != '--damos_quota_goal':
        return []
    if nr_filled_args == 0:
        return _damon.qgoal_metrics
    return []

def damos_filter_candidates(words, cword):
    prev_option, nr_filled_args = prev_option_nr_filed_args(words, cword)
    if not prev_option in ['--damos_filter', '--snapshot_damos_filter']:
        return []
    if nr_filled_args == 0:
        return ['allow', 'reject']
    damos_filter_types = ['active', 'memcg', 'young', 'hugepage_size',
                          'unmapped', 'addr', 'target']
    if nr_filled_args == 1:
        return ['none'] + damos_filter_types
    if nr_filled_args == 2:
        return damos_filter_types
    return []

def damon_param_candidates(words, cword):
    candidates = get_candidates(
            words, cword,
            [
                Option('--ops', 1),
                Option('--monitoring_intervals_autotune', 0),
                Option('--numa_node', -1),
                Option('--monitoring_intervals', 3),
                Option('--monitoring_intervals_goal', 4),
                Option('--monitoring_nr_regions_range', 2),
                Option('--damos_action', 1),
                Option('--damos_apply_interval', 1),
                Option('--damos_quota_interval', 1),
                Option('--damos_quota_space', 1),
                Option('--damos_quota_goal', -1),
                Option('--damos_filter', -1),
                ])
    if candidates:
        return candidates

    prev = words[cword - 1]
    if prev == '--ops':
        return ['vaddr', 'paddr', 'fvaddr']
    if prev == '--damos_action':
        return ['willneed', 'cold', 'pageout', 'hugepage', 'nohugepage',
                'lru_prio', 'lru_deprio', 'migrate_hot', 'migrate_cold',
                'stat']
    candidates = damos_quota_goal_candidates(words, cword)
    if candidates:
        return candidates
    return damos_filter_candidates(words, cword)

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
    if cword < 3:
        return []
    candidates = get_candidates(
            words[3:], cword - 3, [
                Option('--input', 1),
                Option('--snapshot_damos_filter', -1),
                Option('--style', 1),
                ])
    if candidates:
        return candidates
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
    return damos_filter_candidates(words[3:], cword - 3)
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

def monitor_candidates(words, cword):
    candidates = get_candidates(
            words[2:], cword - 2, [
                Option('--report_type', 1),
                Option('--delay', 1),
                Option('--count', 1),
                ])
    if words[cword - 1] == '--report_type':
        candidates = ['heats', 'wss', 'holistic']
    return candidates


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
        candidates = ['start', 'stop', 'tune', 'record', 'report', 'monitor',
                      'help', 'version']
    cmd = words[1]
    if cmd == 'start':
        candidates = start_candidates(words, cword)
    elif cmd == 'tune':
        candidates = tune_candidates(words, cword)
    elif cmd == 'record':
        candidates = record_candidates(words, cword)
    elif cmd == 'report':
        candidates = report_candidates(words, cword)
    elif cmd == 'monitor':
        candidates = monitor_candidates(words, cword)
    elif cmd == 'help':
        candidates = help_candidtes(words, cword)
    if words[cword - 1] != '--help':
        candidates.append('--help')
    print(' '.join(candidates))
    return True
