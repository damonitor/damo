#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import argparse
import unittest

import _test_damo_common

_test_damo_common.add_damo_dir_to_syspath()

import _damon
import _damon_args
import _damon_sysfs

class TestDamonArgs(unittest.TestCase):
    def test_damon_ctx_for(self):
        _damon._damon_fs = _damon_sysfs
        _damon.set_feature_supports({'init_regions': True, 'schemes': True,
                'schemes_stat_qt_exceed': True, 'init_regions_target_idx':
                True, 'schemes_prioritization': True, 'schemes_tried_regions':
                False, 'record': False, 'schemes_quotas': True, 'fvaddr':
                False, 'paddr': True, 'schemes_wmarks': True,
                'schemes_speed_limit': True, 'schemes_stat_succ': True,
                'vaddr': True})

        parser = argparse.ArgumentParser()
        _damon_args.set_argparser(
                parser, add_record_options=False, min_help=True)

        args = parser.parse_args(
                ('--sample 5000 --aggr 100000 --updr 1000000 ' +
                    '--minr 10 --maxr 1000 --regions=123-456 paddr').split())
        err = _damon_args.deduce_target_update_args(args)
        self.assertEqual(err, None)
        ctx, err = _damon_args.damon_ctx_for(args)
        self.assertEqual(err, None)
        self.assertEqual(ctx, _damon.DamonCtx('paddr',
            [_damon.DamonTarget(None, [_damon.DamonRegion(123, 456)])],
            _damon.DamonIntervals(5000, 100000, 1000000),
            _damon.DamonNrRegionsRange(10, 1000), []))

        self.assertEqual(ctx, _damon.DamonCtx('paddr',
            [_damon.DamonTarget(None, [_damon.DamonRegion(123, 456)])],
            _damon.DamonIntervals(5000, 100000, 1000000),
            _damon.DamonNrRegionsRange(10, 1000), []))

        args = parser.parse_args(
                ('--sample 5ms --aggr 100ms --updr 1s ' +
                    '--minr 10 --maxr 1,000 --regions=1K-4K paddr').split())
        err = _damon_args.deduce_target_update_args(args)
        self.assertEqual(err, None)
        ctx, err = _damon_args.damon_ctx_for(args)
        self.assertEqual(err, None)
        self.assertEqual(ctx, _damon.DamonCtx('paddr',
            [_damon.DamonTarget(None, [_damon.DamonRegion(1024, 4096)])],
            _damon.DamonIntervals(5000, 100000, 1000000),
            _damon.DamonNrRegionsRange(10, 1000), []))

        parser = argparse.ArgumentParser()
        _damon_args.set_argparser(
                parser, add_record_options=False, min_help=True)

        args = parser.parse_args(
                ('--sample 5ms --aggr 100ms --updr 1s ' +
                    '--minr 10 --maxr 1,000 --regions=1K-4K ' +
                    '--ops paddr').split())
        ctx, err = _damon_args.damon_ctx_for(args)
        self.assertEqual(err, None)
        self.assertEqual(ctx, _damon.DamonCtx('paddr',
            [_damon.DamonTarget(None, [_damon.DamonRegion(1024, 4096)])],
            _damon.DamonIntervals(5000, 100000, 1000000),
            _damon.DamonNrRegionsRange(10, 1000), []))

    def test_damon_intervals_for(self):
        parser = argparse.ArgumentParser()
        _damon_args.set_monitoring_attrs_argparser(parser)
        _damon_args.set_monitoring_attrs_pinpoint_argparser(parser)

        args = parser.parse_args(
                '--monitoring_intervals 4ms 120ms 1.5s'.split())
        intervals = _damon_args.damon_intervals_for(
                args.monitoring_intervals, args.sample, args.aggr, args.updr,
                args.monitoring_intervals_goal)
        self.assertEqual(intervals, _damon.DamonIntervals('4ms', '120ms',
            '1.5s'))

        args = parser.parse_args('--sample 7ms'.split())
        intervals = _damon_args.damon_intervals_for(
                args.monitoring_intervals, args.sample, args.aggr, args.updr,
                args.monitoring_intervals_goal)

        self.assertEqual(intervals, _damon.DamonIntervals('7ms'))

    def test_damon_nr_regions_range_for(self):
        parser = argparse.ArgumentParser()
        _damon_args.set_monitoring_attrs_argparser(parser)
        _damon_args.set_monitoring_attrs_pinpoint_argparser(parser)

        args = parser.parse_args(
                '--monitoring_nr_regions_range 25 5000'.split())
        nr_range = _damon_args.damon_nr_regions_range_for(
                args.monitoring_nr_regions_range, args.minr, args.maxr)
        self.assertEqual(nr_range, _damon.DamonNrRegionsRange(25, 5000))

    def test_merge_ranges(self):
        merged = _damon_args.merge_ranges(
                [[10, 20], [25, 40], [40, 90], [90, 120], [125, 135],
                 [125, 145], [135, 150]])
        self.assertEqual(merged, [[10, 20], [25, 120], [125, 150]])

    def test_damos_filter_format_v2(self):
        f, e, n = _damon_args.damos_options_to_filter_v2(
                'allow anon'.split())
        self.assertEqual(
                f, _damon.DamosFilter(
                    filter_type='anon', matching=True, allow=True))
        self.assertEqual(n, 2)
        f, e, n = _damon_args.damos_options_to_filter_v2(
                'allow none anon'.split())
        self.assertEqual(
                f, _damon.DamosFilter(
                    filter_type='anon', matching=False, allow=True))
        self.assertEqual(n, 3)
        f, e, n = _damon_args.damos_options_to_filter_v2(
                'reject none anon'.split())
        self.assertEqual(
                f, _damon.DamosFilter(
                    filter_type='anon', matching=False, allow=False))
        self.assertEqual(n, 3)
        f, e, n = _damon_args.damos_options_to_filter_v2(
                'allow memcg a/b/c'.split())
        self.assertEqual(
                f, _damon.DamosFilter(
                    filter_type='memcg', matching=True, allow=True,
                    memcg_path='a/b/c'))
        self.assertEqual(n, 3)

    def test_convert_damos_filter_v1_to_v2(self):
        question_expects = [
                ['anon matching', 'reject anon'],
                ['anon matching allow', 'allow anon'],
                ['anon matching reject', 'reject anon'],
                ['anon nomatching', 'reject none anon'],
                ['anon nomatching allow', 'allow none anon'],
                ['anon nomatching reject', 'reject none anon'],

                ['memcg matching a/b/c', 'reject memcg a/b/c'],
                ['memcg matching a/b/c allow', 'allow memcg a/b/c'],
                ['memcg matching a/b/c reject', 'reject memcg a/b/c'],
                ['memcg nomatching a/b/c', 'reject none memcg a/b/c'],
                ['memcg nomatching a/b/c allow', 'allow none memcg a/b/c'],
                ['memcg nomatching a/b/c reject', 'reject none memcg a/b/c'],

                ['young matching', 'reject young'],
                ['young matching allow', 'allow young'],
                ['young matching reject', 'reject young'],
                ['young nomatching', 'reject none young'],
                ['young nomatching allow', 'allow none young'],
                ['young nomatching reject', 'reject none young'],

                ['addr matching 123 567', 'reject addr 123 567'],
                ['addr matching 123 567 allow', 'allow addr 123 567'],
                ['addr matching 123 567 reject', 'reject addr 123 567'],
                ['addr nomatching 123 567', 'reject none addr 123 567'],
                ['addr nomatching 123 567 allow', 'allow none addr 123 567'],
                ['addr nomatching 123 567 reject', 'reject none addr 123 567'],

                ['target matching 1', 'reject target 1'],
                ['target matching 1 allow', 'allow target 1'],
                ['target matching 1 reject', 'reject target 1'],
                ['target nomatching 1', 'reject none target 1'],
                ['target nomatching 1 allow', 'allow none target 1'],
                ['target nomatching 1 reject', 'reject none target 1'],

                ]
        for question, expect in question_expects:
            answer, err = _damon_args.convert_damos_filter_v1_to_v2(
                    question.split())
            self.assertEqual(err, None)
            self.assertEqual(answer, expect.split())

    def test_damos_options_to_filters(self):
        question_expects = [
                [['anon matching', 'reject anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=True, allow=False)],
                [['anon matching allow', 'allow anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=True, allow=True)],
                [['anon matching reject', 'reject anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=True, allow=False)],
                [['anon nomatching', 'reject none anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=False, allow=False)],
                [['anon nomatching allow', 'allow none anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=False, allow=True)],
                [['anon nomatching reject', 'reject none anon'],
                 _damon.DamosFilter(
                     filter_type='anon', matching=False, allow=False)],

                [['memcg matching a/b/c', 'reject memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=True, allow=False,
                     memcg_path='a/b/c')],
                [['memcg matching a/b/c allow', 'allow memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=True, allow=True,
                     memcg_path='a/b/c')],
                [['memcg matching a/b/c reject', 'reject memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=True, allow=False,
                     memcg_path='a/b/c')],
                [['memcg nomatching a/b/c', 'reject none memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=False, allow=False,
                     memcg_path='a/b/c')],
                [['memcg nomatching a/b/c allow', 'allow none memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=False, allow=True,
                     memcg_path='a/b/c')],
                [['memcg nomatching a/b/c reject', 'reject none memcg a/b/c'],
                 _damon.DamosFilter(
                     filter_type='memcg', matching=False, allow=False,
                     memcg_path='a/b/c')],

                [['young matching', 'reject young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=True, allow=False)],
                [['young matching allow', 'allow young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=True, allow=True)],
                [['young matching reject', 'reject young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=True, allow=False)],
                [['young nomatching', 'reject none young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=False, allow=False)],
                [['young nomatching allow', 'allow none young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=False, allow=True)],
                [['young nomatching reject', 'reject none young'],
                 _damon.DamosFilter(
                     filter_type='young', matching=False, allow=False)],

                [['addr matching 123 456', 'reject addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=True, allow=False,
                     address_range=_damon.DamonRegion(123, 456))],
                [['addr matching 123 456 allow', 'allow addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=True, allow=True,
                     address_range=_damon.DamonRegion(123, 456))],
                [['addr matching 123 456 reject', 'reject addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=True, allow=False,
                     address_range=_damon.DamonRegion(123, 456))],
                [['addr nomatching 123 456', 'reject none addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=False, allow=False,
                     address_range=_damon.DamonRegion(123, 456))],
                [['addr nomatching 123 456 allow', 'allow none addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=False, allow=True,
                     address_range=_damon.DamonRegion(123, 456))],
                [['addr nomatching 123 456 reject', 'reject none addr 123 456'],
                 _damon.DamosFilter(
                     filter_type='addr', matching=False, allow=False,
                     address_range=_damon.DamonRegion(123, 456))],

                [['target matching 1', 'reject target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=True, allow=False,
                     damon_target_idx='1')],
                [['target matching 1 allow', 'allow target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=True, allow=True,
                     damon_target_idx='1')],
                [['target matching 1 reject', 'reject target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=True, allow=False,
                     damon_target_idx='1')],
                [['target nomatching 1', 'reject none target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=False, allow=False,
                     damon_target_idx='1')],
                [['target nomatching 1 allow', 'allow none target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=False, allow=True,
                     damon_target_idx='1')],
                [['target nomatching 1 reject', 'reject none target 1'],
                 _damon.DamosFilter(
                     filter_type='target', matching=False, allow=False,
                     damon_target_idx='1')],
                ]
        for questions, expect in question_expects:
            for question in questions:
                answer, err = _damon_args.damos_options_to_filters(
                        [question.split()])
                self.assertEqual(err, None)
                self.assertEqual(answer, [expect])

if __name__ == '__main__':
    unittest.main()
