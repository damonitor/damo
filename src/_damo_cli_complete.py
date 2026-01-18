# SPDX-License-Identifier: GPL-2.0

import datetime
import os
import sys

def log(msg):
    msg = '%s: %s' % (datetime.datetime.now(), msg)
    with open('.damo_cli_complete_log', 'a') as f:
        f.write('%s\n' % msg)

def handle_report(words, cword):
    if cword == 2:
        print('access damon holistic heatmap sysinfo')
        return
    report_type = words[2]
    if report_type == 'access':
        if cword == 3:
            print('--input --snapshot_damos_filter --style')
            return
        if cword == 4:
            option = words[3]
            if option == '--input':
                candidates = ['tried_regions_of', './', '../']
                for f in os.listdir('./'):
                    candidates.append('./%s' % f)
                print(' '.join(candidates))
                return
            if option == '--style':
                print(' '.join([
                    'detailed', 'simple-boxes', 'temperature-sz-hist',
                    'recency-sz-hist', 'cold-memory-tail',
                    'recency-percentiles', 'idle-time-percentiles',
                    'temperature-percentiles', 'cold', 'hot']))
                return

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
    if cword == 1:
        print('start stop tune record report help version')
    cmd = words[1]
    if cmd == 'report':
        handle_report(words, cword)
    return True
