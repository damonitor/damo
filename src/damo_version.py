# SPDX-License-Identifier: GPL-2.0

__version__ = '3.0.5'

def get_release_version():
    return __version__

def main(args):
    # todo: print 'git describe' if git repo version is being used.
    print(get_release_version())

def set_argparser(parser):
    return parser
