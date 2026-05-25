#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import unittest

import _test_damo_common

_test_damo_common.add_damo_dir_to_syspath()

import damo_report_trace

class TestDamoReportTrace(unittest.TestCase):
    def test_fmt_damon_region_aggregated(self):
        self.assertEqual(damo_report_trace.fmt_damon_region_aggregated(
            '2452.789 kdamond.0/2149 damon:damon_region_aggregated(target_id=0 nr_regions=11 8354394112-8372879360: 0 600 probe_hits=13 00)'.split(), 'damo-report-trace-perf'),
                         '2452.789 kdamond.0/2149 damon_region_aggregated 0 0/11 7.780636 GiB (17.628906 MiB) 0 600 19 0')

if __name__ == '__main__':
    unittest.main()
