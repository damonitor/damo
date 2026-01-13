# SPDX-License-Identifier: GPL-2.0

import os
import subprocess

__version__ = '3.1.1'

def get_release_version():
    return __version__

# Because this module is used from packaging/setup.py, _damo_*.py modules on
# src/ directory cannot be imported.  Otherwise, packaging/build.sh fails.
# Implement avail_cmd() here.
def avail_cmd(cmd):
    try:
        subprocess.check_output(['which', cmd], stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def get_real_version():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    damo_dir = os.path.dirname(src_dir)
    git_dir = os.path.join(damo_dir, '.git')
    if not os.path.isdir(git_dir):
        return get_release_version()
    if not avail_cmd('git'):
        return get_release_version()
    try:
        return subprocess.check_output(
                ['git', '--git-dir', git_dir, 'describe']).decode().strip()
    except subprocess.CalledProcessError:
        return get_release_version()

def main(args):
    print(get_release_version())

def set_argparser(parser):
    return parser
