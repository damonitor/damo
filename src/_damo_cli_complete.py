# SPDX-License-Identifier: GPL-2.0

import sys

def handle_cli_complete():
    if len(sys.argv) < 4:
        return False
    if sys.argv[1] != '--cli_complete':
        return False
    cword = int(sys.argv[2])
    if cword == 1:
        print('start stop tune record report help version')

    return True
