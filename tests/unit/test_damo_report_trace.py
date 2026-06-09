#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import unittest

import _test_damo_common

_test_damo_common.add_damo_dir_to_syspath()

import damo_report_trace

class TestDamoReportTrace(unittest.TestCase):
    def test_fmt_damon_region_aggregated_trace(self):
        damo_report_trace.region_aggregated_idx = 0
        self.assertEqual(damo_report_trace.fmt_damon_region_aggregated_trace(
            'target_id=0 nr_regions=11 0-4096: 0 600 probe_hits=13 00'.split()),
            '0 0/11 0 B (4.000000 KiB) 0 600 19 0')
        self.assertEqual(damo_report_trace.fmt_damon_region_aggregated_trace(
            'target_id=0 nr_regions=11 4096-12288: 13 27 probe_hits=12 0f'.split()),
            '0 1/11 4.000000 KiB (8.000000 KiB) 13 27 18 15')

    def test_parse_trace_line(self):
        outputs = damo_report_trace.parse_trace_line(
                '  1241.509 kdamond.0/102481 damon:damon_aggregated(target_id=0 nr_regions=11 8232701952-8371830784: 0 1485)', 'perf')
        self.assertEqual(outputs, (
            '1241.509', 'kdamond.0/102481', 'damon:damon_aggregated',
            'target_id=0 nr_regions=11 8232701952-8371830784: 0 1485'.split()))

        outputs = damo_report_trace.parse_trace_line(
                '           <...>-102481 [006] ..... 99141.640633: damon_aggregated:     target_id=0 nr_regions=12 4185931776-5007028224: 0 2022',
                'trace-cmd')
        self.assertEqual(outputs, (
            '99141.640633', '<...>-102481', 'damon:damon_aggregated',
            'target_id=0 nr_regions=12 4185931776-5007028224: 0 2022'.split()))

        # trace-cmd report output on some versions of trace-cmd including
        # 3.2-1ubuntu2 omits the flags field.
        outputs = damo_report_trace.parse_trace_line(
                '           <...>-102481 [006] 99141.640633: damon_aggregated:     target_id=0 nr_regions=12 4185931776-5007028224: 0 2022',
                'trace-cmd')
        self.assertEqual(outputs, (
            '99141.640633', '<...>-102481', 'damon:damon_aggregated',
            'target_id=0 nr_regions=12 4185931776-5007028224: 0 2022'.split()))

if __name__ == '__main__':
    unittest.main()
