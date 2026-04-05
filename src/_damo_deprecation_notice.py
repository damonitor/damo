# SPDX-License-Identifier: GPL-2.0

import sys

contact_message = '''
    If you depend on those, please report your usecase to GitHub Issues [1],
    sj@kernel.org, damon@lists.linux.dev and/or linux-mm@kvack.org.

    [1] https://github.com/damonitor/damo/issues

'''

def will_be_deprecated(feature, deadline, additional_notice='',
                       alternative=None):
    lines = [
            '',
            'WARNING: %s will be deprecated by %s.' % (feature, deadline)
            ]
    if alternative:
        lines.append('    Use "%s" instead.' % alternative)
    if additional_notice:
        lines.append(additional_notice)
    lines.append(contact_message)
    sys.stderr.write('\n'.join(lines))

def deprecated(feature, deadline, alternative=None, do_exit=False, exit_code=1,
        additional_notice=''):
    lines = [
            'WARNING: %s is deprecated.' % feature,
            '    The support will be removed by %s.' % deadline,
            ]
    if alternative:
        lines.append('    Use "%s" instead.' % alternative)
    if additional_notice:
        lines.append(additional_notice)
    lines.append(contact_message)
    sys.stderr.write('\n'.join(lines))
    if do_exit:
        exit(exit_code)
