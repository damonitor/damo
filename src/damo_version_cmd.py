# SPDX-License-Identifier: GPL-2.0

import damo_version

def main(args):
    # todo: print 'git describe' if git repo version is being used.
    print(damo_version.__version__)

def set_argparser(parser):
    return parser
