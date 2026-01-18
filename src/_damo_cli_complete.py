# SPDX-License-Identifier: GPL-2.0

import datetime
import sys

def log(msg):
    msg = '%s: %s' % (datetime.datetime.now(), msg)
    with open('.damo_cli_complete_log', 'a') as f:
        f.write('%s\n' % msg)

def handle_cli_complete():
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
        if cword == 2:
            print('access damon holistic heatmap sysinfo')

    return True
