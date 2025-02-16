# SPDX-License-Identifier: GPL-2.0

import subprocess

def avail_cmd(cmd):
    try:
        subprocess.check_output(['which', cmd], stderr=subprocess.DEVNULL)
        return True
    except:
        return False
