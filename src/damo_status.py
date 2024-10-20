# SPDX-License-Identifier: GPL-2.0

"""
Show status of DAMON.
"""

import _damo_deprecation_notice
import damo_report_damon

def main(args):
    '''
    'damo status' will be deprecated in favor of 'damo report damon'.  To
    avoid unnecessary changes to 'damo_status.py' before it is officially
    deprecated and removed, make this source file to work as just a wrapper of
    'damo_report_damon.py'.

    Another appraoch would be simply removing this file and updating 'damo.py'
    to keep 'status' command, but link 'damo_report_kdamodsn.py' file.  We
    don't use the approach to keep this file as a place to add deprecation
    message later.
    '''
    _damo_deprecation_notice.will_be_deprecated(
            feature='"damo status"', deadline='2025-01-20',
            additional_notice='Use "damo report damon" instead.')
    return damo_report_damon.main(args)

def set_argparser(parser):
    return damo_report_damon.set_argparser(parser)
