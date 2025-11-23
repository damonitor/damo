# SPDX-License-Identifier: GPL-2.0

import os
import subprocess

import _damo_subproc

__version__ = '3.0.5'

def get_release_version():
    return __version__

def get_real_version():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    damo_dir = os.path.dirname(src_dir)
    git_dir = os.path.join(damo_dir, '.git')
    if not os.path.isdir(git_dir):
        return get_release_version()
    if not _damo_subproc.avail_cmd('git'):
        return get_release_version()
    return subprocess.check_output(
            ['git', '--git-dir', git_dir, 'describe']).decode().strip()

def main(args):
    print(get_release_version())

def set_argparser(parser):
    return parser
