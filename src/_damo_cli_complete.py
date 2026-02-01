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
    repeatable = None

    # List of positional candidates for this option's arguments.
    # e.g., [['foo', 'bar'], None, ['baz', 'bow']] means for the first
    # argument, 'foo' or 'bar' can be entered.  No suggestion for the second
    # argument.  For third argument, 'baz' and 'bow' can be entered.
    positional_candidates = None

    # List of non-positional candidastes for this option's arguments.
    # e.g., ['foo', 'bar'] means for any argument for this option, 'foo' and
    # 'bar' can be suggested.
    non_positional_candidates = None

    def __init__(self, name, nr_args, repeatable=True,
                 positional_candidates=None,
                 non_positional_candidates=None):
        self.name = name
        self.nr_args = nr_args
        self.repeatable = repeatable
        self.positional_candidates = positional_candidates
        self.non_positional_candidates = non_positional_candidates

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

def option_arg_candidates(words, cword, options):
    prev_option, nr_filled_args = prev_option_nr_filed_args(words, cword)
    candidates = []
    for option in options:
        if option.name != prev_option:
            continue
        if option.non_positional_candidates is not None:
            candidates += option.non_positional_candidates
        if option.positional_candidates is None:
            continue
        if len(option.positional_candidates) > nr_filled_args:
            if option.positional_candidates[nr_filled_args] is not None:
                candidates += option.positional_candidates[nr_filled_args]
    return candidates

def get_candidates(words, cword, options):
    '''
    words and cword should start from the options part (no command).
    options should be a list of Option objects.
    '''
    if can_suggest_options(words, cword, options) is False:
        return option_arg_candidates(words, cword, options)
    candidates = []
    for option in options:
        if option.repeatable is False and option.name in words[:cword]:
            continue
        candidates.append(option.name)
    return candidates

damos_filter_types = ['active', 'memcg', 'young', 'hugepage_size', 'unmapped',
                      'addr', 'target']
damos_filter_positional_candids = [
        ['allow', 'reject'], ['none'] + damos_filter_types,
        # todo: do not suggest unless 'none' was entered
        damos_filter_types]

def damon_param_candidates(words, cword):
    return get_candidates(
            words, cword,
            [
                Option('--ops', 1, True, [['vaddr', 'paddr', 'fvaddr']]),
                Option('--monitoring_intervals_autotune', 0, False),
                Option('--numa_node', -1, True),
                Option('--monitoring_intervals', 3, True),
                Option('--monitoring_intervals_goal', 4, True),
                Option('--monitoring_nr_regions_range', 2, True),
                Option('--damos_action', 1, True,
                       [['willneed', 'cold', 'pageout', 'hugepage',
                         'nohugepage', 'lru_prio', 'lru_deprio', 'migrate_hot',
                         'migrate_cold', 'stat']]
                       ),
                Option('--damos_apply_interval', 1, True),
                Option('--damos_quota_interval', 1, True),
                Option('--damos_quota_space', 1, True),
                Option('--damos_quota_goal', -1, True, [_damon.qgoal_metrics]),
                Option('--damos_filter', -1, True,
                       damos_filter_positional_candids),
                ])

def start_candidates(words, cword):
    return damon_param_candidates(words[2:], cword - 2)

def tune_candidates(words, cword):
    return damon_param_candidates(words[2:], cword - 2)

def record_candidates(words, cword):
    return get_candidates(
            words[2:], cword - 2,
            [Option('--out', 1, False, None),
             Option('--snapshot', 2, False, None),
             Option('--timeout', 1, False, None),
             Option('--snapshot_damos_filter', -1, False,
                    damos_filter_positional_candids),
             ])

def report_access_candidates(words, cword):
    if cword < 3:
        return []
    candidates = get_candidates(
            words[3:], cword - 3, [
                Option('--input', 1, True),
                Option('--snapshot_damos_filter', -1, True,
                       damos_filter_positional_candids),
                Option('--style', 1, False,
                       [['detailed', 'simple-boxes', 'temperature-sz-hist',
                         'recency-sz-hist', 'cold-memory-tail',
                         'recency-percentiles', 'idle-time-percentiles',
                         'temperature-percentiles', 'cold', 'hot']]
                       ),
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
    return []

def report_damon_candidates(words, cword):
    return get_candidates(
            words[3:], cword - 3,
            [Option('--format', 1, False, [['json', 'yaml', 'report']]),
             Option('--show_cpu_usage', 0, False, None),
             Option('--kdamonds_summary', 0, False, None),
             ])

def report_sysinfo_candidates(words, cword):
    return get_candidates(
            words[3:], cword - 3,
            [Option('--print', -1, False, None,
                    non_positional_candidates= [
                        'versions', 'fs_info', 'trace_cmd_info', 'perf_info',
                        'sysfs_features', 'debugfs_features', 'trace_features',
                        'modules', 'all']
                    ),
             Option('--invalidate_cache', 0, False, None),
             ])

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
                Option('--report_type', 1, False,
                       [['heats', 'wss', 'holistic']]),
                Option('--delay', 1, False),
                Option('--count', 1, False),
                ])
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
