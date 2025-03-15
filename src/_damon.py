# SPDX-License-Identifier: GPL-2.0

"""
Contains core functions for DAMON control.
"""

import collections
import copy
import json
import os
import random
import subprocess
import time

import _damo_fmt_str
import damo_version

# Core data structures

class DamonIntervalsGoal:
    access_bp = None
    aggrs = None
    min_sample_us = None
    max_sample_us = None

    def __init__(self, access_bp='0%', aggrs=0, min_sample_us=0, max_sample_us=0):
        self.access_bp = _damo_fmt_str.text_to_bp(access_bp)
        self.aggrs = _damo_fmt_str.text_to_nr(aggrs)
        self.min_sample_us = _damo_fmt_str.text_to_us(min_sample_us)
        self.max_sample_us = _damo_fmt_str.text_to_us(max_sample_us)

    def to_str(self, raw):
        return 'target %s accesses per %s aggrs, [%s, %s] sampling interval' % (
                _damo_fmt_str.format_bp(self.access_bp, raw),
                _damo_fmt_str.format_nr(self.aggrs, raw),
                _damo_fmt_str.format_time_us(self.min_sample_us, raw),
                _damo_fmt_str.format_time_us(self.max_sample_us, raw))

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    @classmethod
    def from_kvpairs(cls, kvpairs):
        return DamonIntervalsGoal(
                kvpairs['access_bp'], kvpairs['aggrs'],
                kvpairs['min_sample_us'], kvpairs['max_sample_us'])

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('access_bp', _damo_fmt_str.format_bp(self.access_bp, raw)),
            ('aggrs', _damo_fmt_str.format_nr(self.aggrs, raw)),
            ('min_sample_us', _damo_fmt_str.format_time_us(
                self.min_sample_us, raw)),
            ('max_sample_us', _damo_fmt_str.format_time_us(
                self.max_sample_us, raw)),
            ])

    def enabled(self):
        return self.aggrs != 0

class DamonIntervals:
    sample = None
    aggr = None
    ops_update = None
    intervals_goal = None

    def __init__(self, sample='5ms', aggr='100ms', ops_update='1s',
                 intervals_goal=DamonIntervalsGoal()):
        self.sample = _damo_fmt_str.text_to_us(sample)
        self.aggr = _damo_fmt_str.text_to_us(aggr)
        self.ops_update = _damo_fmt_str.text_to_us(ops_update)
        self.intervals_goal = intervals_goal

    def to_str(self, raw):
        lines = ['sample %s, aggr %s, update %s' % (
                _damo_fmt_str.format_time_us(self.sample, raw),
                _damo_fmt_str.format_time_us(self.aggr, raw),
                _damo_fmt_str.format_time_us(self.ops_update, raw))]
        if self.intervals_goal.enabled():
            lines.append('%s' % self.intervals_goal.to_str(raw))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    @classmethod
    def from_kvpairs(cls, kvpairs):
        if not 'intervals_goal' in kvpairs:
            return DamonIntervals(
                    kvpairs['sample_us'], kvpairs['aggr_us'],
                    kvpairs['ops_update_us'])
        return DamonIntervals(
                kvpairs['sample_us'], kvpairs['aggr_us'],
                kvpairs['ops_update_us'],
                DamonIntervalsGoal.from_kvpairs(kvpairs['intervals_goal']))

    def to_kvpairs(self, raw=False, omit_defaults=False):
        kvp = collections.OrderedDict([
            ('sample_us', _damo_fmt_str.format_time_us(self.sample, raw)),
            ('aggr_us', _damo_fmt_str.format_time_us(self.aggr, raw)),
            ('ops_update_us',
                _damo_fmt_str.format_time_us(self.ops_update, raw))])
        if not omit_defaults or self.intervals_goal != DamonIntervalsGoal():
            kvp['intervals_goal'] = self.intervals_goal.to_kvpairs(raw)
        return kvp

class DamonNrRegionsRange:
    minimum = None
    maximum = None

    def __init__(self, min_=10, max_=1000):
        self.minimum = _damo_fmt_str.text_to_nr(min_)
        self.maximum = _damo_fmt_str.text_to_nr(max_)

    def to_str(self, raw):
        return '[%s, %s]' % (
                _damo_fmt_str.format_nr(self.minimum, raw),
                _damo_fmt_str.format_nr(self.maximum, raw))

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    @classmethod
    def from_kvpairs(cls, kvpairs):
        return DamonNrRegionsRange(kvpairs['min'], kvpairs['max'])

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('min', _damo_fmt_str.format_nr(self.minimum, raw)),
            ('max', _damo_fmt_str.format_nr(self.maximum, raw)),
            ])

unit_percent = 'percent'
unit_samples = 'samples'
unit_usec = 'usec'
unit_aggr_intervals = 'aggr_intervals'

class DamonNrAccesses:
    samples = None
    percent = None

    def __init__(self, val, unit):
        if val == None or unit == None:
            return
        if unit == unit_samples:
            self.samples = _damo_fmt_str.text_to_nr(val)
        elif unit == unit_percent:
            self.percent = _damo_fmt_str.text_to_percent(val)
        else:
            raise Exception('invalid DamonNrAccesses unit \'%s\'' % unit)

    def __eq__(self, other):
        return (type(self) == type(other) and
                ((self.samples != None and self.samples == other.samples) or
                    (self.percent != None and self.percent == other.percent)))

    def add_unset_unit(self, intervals):
        if self.samples != None and self.percent != None:
            return
        max_val = intervals.aggr / intervals.sample
        if self.samples == None:
            self.samples = int(self.percent * max_val / 100)
        elif self.percent == None:
            self.percent = int(self.samples * 100.0 / max_val)

    def to_str(self, unit, raw):
        if unit == unit_percent:
            return '%s %%' % (_damo_fmt_str.format_nr(self.percent, raw))
        elif unit == unit_samples:
            return '%s %s' % (_damo_fmt_str.format_nr(self.samples, raw),
                    unit_samples)
        raise Exception('unsupported unit for NrAccesses (%s)' % unit)

    @classmethod
    def from_kvpairs(cls, kv):
        ret = DamonNrAccesses(None, None)
        if 'samples' in kv and kv['samples'] != None:
            ret.samples = _damo_fmt_str.text_to_nr(kv['samples'])
        if 'percent' in kv and kv['percent'] != None:
            ret.percent = _damo_fmt_str.text_to_percent(kv['percent'])
        return ret

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict(
                [('samples', self.samples), ('percent', self.percent)])

class DamonAge:
    usec = None
    aggr_intervals = None

    def __init__(self, val, unit):
        if val == None and unit != None:
            self.unit = unit
            return
        if val == None and unit == None:
            return
        if unit == unit_usec:
            self.usec = _damo_fmt_str.text_to_us(val)
        elif unit == unit_aggr_intervals:
            self.aggr_intervals = _damo_fmt_str.text_to_nr(val)
        else:
            raise Exception('DamonAge unsupported unit (%s)' % unit)

    def __eq__(self, other):
        return (type(self) == type(other) and
                ((self.usec != None and self.usec == other.usec) or
                    (self.aggr_intervals != None and
                        self.aggr_intervals == other.aggr_intervals)))

    def add_unset_unit(self, intervals):
        if self.usec != None and self.aggr_intervals != None:
            return
        if self.usec == None:
            self.usec = self.aggr_intervals * intervals.aggr
        elif self.aggr_intervals == None:
            self.aggr_intervals = int(self.usec / intervals.aggr)

    def to_str(self, unit, raw):
        if unit == unit_usec:
            return _damo_fmt_str.format_time_us_exact(self.usec, raw)
        return '%s %s' % (_damo_fmt_str.format_nr(self.aggr_intervals, raw),
                unit_aggr_intervals)

    @classmethod
    def from_kvpairs(cls, kv):
        ret = DamonAge(None, None)
        if kv['usec'] != None:
            ret.usec = _damo_fmt_str.text_to_us(kv['usec'])
        if kv['aggr_intervals'] != None:
            ret.aggr_intervals = _damo_fmt_str.text_to_nr(kv['aggr_intervals'])
        return ret

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict(
                [('usec', _damo_fmt_str.format_time_us_exact(self.usec, raw)
                    if self.usec != None else None),
                    ('aggr_intervals',
                        _damo_fmt_str.format_nr(self.aggr_intervals, raw)
                        if self.aggr_intervals != None else None)])

class DamonRegion:
    # [start, end)
    start = None
    end = None
    # nr_accesses and age could be None
    nr_accesses = None
    age = None
    sz_filter_passed = None
    scheme = None # non-None if tried region

    def __init__(self, start, end, nr_accesses=None, nr_accesses_unit=None,
            age=None, age_unit=None, sz_filter_passed=0):
        self.start = _damo_fmt_str.text_to_bytes(start)
        self.end = _damo_fmt_str.text_to_bytes(end)

        if nr_accesses == None:
            return
        self.nr_accesses = DamonNrAccesses(nr_accesses, nr_accesses_unit)
        self.age = DamonAge(age, age_unit)
        self.sz_filter_passed = sz_filter_passed

    def to_str(self, raw, intervals=None):
        if self.nr_accesses == None:
            return _damo_fmt_str.format_addr_range(self.start, self.end, raw)

        if intervals != None:
            self.nr_accesses.add_unset_unit(intervals)
            self.age.add_unset_unit(intervals)

        if raw == False and intervals != None:
            nr_accesses_unit = unit_percent
            age_unit = unit_usec
        else:
            nr_accesses_unit = unit_samples
            age_unit = unit_aggr_intervals
        str = '%s: nr_accesses: %s, age: %s' % (
                _damo_fmt_str.format_addr_range(self.start, self.end, raw),
                self.nr_accesses.to_str(nr_accesses_unit, raw),
                self.age.to_str(age_unit, raw))
        if self.sz_filter_passed is not None:
            str += ', filter_passed: %s' % _damo_fmt_str.format_sz(
                    self.sz_filter_passed, raw)
        return str

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        if self.nr_accesses == None:
            return type(self) == type(other) and '%s' % self == '%s' % other

    # For aggregate_snapshots() support
    def __hash__(self):
        identification = '%s-%s' % (self.start, self.end)
        return hash(identification)

    @classmethod
    def from_kvpairs(cls, kvpairs):
        if not 'nr_accesses' in kvpairs:
            return DamonRegion(kvpairs['start'], kvpairs['end'])
        region = DamonRegion(kvpairs['start'], kvpairs['end'])
        region.nr_accesses = DamonNrAccesses.from_kvpairs(
                kvpairs['nr_accesses'])
        region.age = DamonAge.from_kvpairs(kvpairs['age'])
        if 'sz_filter_passed' in kvpairs:
            region.sz_filter_passed = _damo_fmt_str.text_to_bytes(
                    kvpairs['sz_filter_passed'])
        else:
            region.sz_filter_passed = 0
        return region

    def to_kvpairs(self, raw=False):
        if self.nr_accesses == None:
            return collections.OrderedDict([
                ('start', _damo_fmt_str.format_nr(self.start, raw)),
                ('end', _damo_fmt_str.format_nr(self.end, raw))])
        return collections.OrderedDict([
            ('start', _damo_fmt_str.format_nr(self.start, raw)),
            ('end', _damo_fmt_str.format_nr(self.end, raw)),
            ('nr_accesses', self.nr_accesses.to_kvpairs(raw)),
            ('age', self.age.to_kvpairs(raw)),
            ('sz_filter_passed', _damo_fmt_str.format_sz(
                self.sz_filter_passed, raw)),
            ])

    def size(self):
        return self.end - self.start

class DamonTarget:
    pid = None
    regions = None
    context = None

    def __init__(self, pid, regions):
        self.pid = pid
        self.regions = regions

    def to_str(self, raw):
        lines = []
        if self.pid is not None:
            lines.append('pid: %s' % self.pid)
        for region in self.regions:
            lines.append('region %s' % region.to_str(raw))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    @classmethod
    def from_kvpairs(cls, kvpairs):
        regions = [DamonRegion.from_kvpairs(kvp) for kvp in kvpairs['regions']]
        return DamonTarget(kvpairs['pid'], regions)

    def to_kvpairs(self, raw=False):
        kvp = collections.OrderedDict()
        kvp['pid'] = self.pid
        kvp['regions'] = [r.to_kvpairs(raw) for r in self.regions]
        return kvp

class DamosAccessPattern:
    sz_bytes = None
    nr_acc_min_max = None # [min/max DamonNrAccesses]
    nr_accesses_unit = None
    age_min_max = None # [min/max DamonAge]
    age_unit = None

    # every region by default, so that it can be used for monitoring
    def __init__(self, sz_bytes=['min', 'max'],
            nr_accesses=['min', 'max'], nr_accesses_unit=unit_percent,
            age=['min', 'max'], age_unit=unit_usec):
        self.sz_bytes = [_damo_fmt_str.text_to_bytes(sz_bytes[0]),
                _damo_fmt_str.text_to_bytes(sz_bytes[1])]

        self.nr_acc_min_max = [
                DamonNrAccesses(nr_accesses[0], nr_accesses_unit),
                DamonNrAccesses(nr_accesses[1], nr_accesses_unit)]
        self.nr_accesses_unit = nr_accesses_unit
        self.age_min_max = [
                DamonAge(age[0], age_unit), DamonAge(age[1], age_unit)]
        self.age_unit = age_unit

    def to_str(self, raw):
        lines = [
            'sz: [%s, %s]' % (_damo_fmt_str.format_sz(self.sz_bytes[0], raw),
                _damo_fmt_str.format_sz(self.sz_bytes[1], raw)),
            ]
        lines.append('nr_accesses: [%s, %s]' % (
            self.nr_acc_min_max[0].to_str(self.nr_accesses_unit, raw),
            self.nr_acc_min_max[1].to_str(self.nr_accesses_unit, raw)))
        lines.append('age: [%s, %s]' % (
            self.age_min_max[0].to_str(self.age_unit, raw),
            self.age_min_max[1].to_str(self.age_unit, raw)))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.sz_bytes == other.sz_bytes and
                self.nr_acc_min_max == other.nr_acc_min_max and
                self.age_min_max == other.age_min_max)

    @classmethod
    def from_kvpairs(cls, kv):
        sz_bytes = [_damo_fmt_str.text_to_bytes(kv['sz_bytes']['min']),
                _damo_fmt_str.text_to_bytes(kv['sz_bytes']['max'])]

        kv_ = kv['nr_accesses']
        try:
            nr_accesses = [_damo_fmt_str.text_to_percent(kv_['min']),
                    _damo_fmt_str.text_to_percent(kv_['max'])]
            nr_accesses_unit = unit_percent
        except:
            min_, nr_accesses_unit = _damo_fmt_str.text_to_nr_unit(kv_['min'])
            max_, nr_accesses_unit2 = _damo_fmt_str.text_to_nr_unit(kv_['max'])
            if nr_accesses_unit != nr_accesses_unit2:
                raise Exception('nr_accesses units should be same')
            nr_accesses = [min_, max_]

        kv_ = kv['age']
        try:
            age = [_damo_fmt_str.text_to_us(kv_['min']),
                    _damo_fmt_str.text_to_us(kv_['max'])]
            age_unit = unit_usec
        except:
            min_age, age_unit = _damo_fmt_str.text_to_nr_unit(kv_['min'])
            max_age, age_unit2 = _damo_fmt_str.text_to_nr_unit(kv_['max'])
            if age_unit != age_unit2:
                raise Exception('age units should be same')
            age = [min_age, max_age]

        return DamosAccessPattern(sz_bytes, nr_accesses, nr_accesses_unit, age,
                age_unit)

    def to_kvpairs(self, raw=False):
        min_nr_accesses = self.nr_acc_min_max[0].to_str(
                self.nr_accesses_unit, raw)
        max_nr_accesses = self.nr_acc_min_max[1].to_str(
                self.nr_accesses_unit, raw)
        min_age = self.age_min_max[0].to_str(self.age_unit, raw)
        max_age = self.age_min_max[1].to_str(self.age_unit, raw)

        return collections.OrderedDict([
            ('sz_bytes', (collections.OrderedDict([
                ('min', _damo_fmt_str.format_sz(self.sz_bytes[0], raw)),
                ('max', _damo_fmt_str.format_sz(self.sz_bytes[1], raw))]))),
            ('nr_accesses', (collections.OrderedDict([
                ('min', min_nr_accesses), ('max', max_nr_accesses)]))),
            ('age', (collections.OrderedDict([
                ('min', min_age), ('max', max_age)]))),
            ])

    def convert_for_units(self, nr_accesses_unit, age_unit, intervals):
        self.nr_acc_min_max[0].add_unset_unit(intervals)
        self.nr_acc_min_max[1].add_unset_unit(intervals)
        self.age_min_max[0].add_unset_unit(intervals)
        self.age_min_max[1].add_unset_unit(intervals)
        self.nr_accesses_unit = nr_accesses_unit
        self.age_unit = age_unit

    def converted_for_units(self, nr_accesses_unit, age_unit, intervals):
        copied = copy.deepcopy(self)
        copied.convert_for_units(nr_accesses_unit, age_unit, intervals)
        return copied

    def effectively_equal(self, other, intervals):
        return (
                self.converted_for_units(
                    unit_samples, unit_aggr_intervals, intervals) ==
                other.converted_for_units(
                    unit_samples, unit_aggr_intervals, intervals))

qgoal_user_input = 'user_input'
qgoal_some_mem_psi_us = 'some_mem_psi_us'
qgoal_node_mem_used_bp = 'node_mem_used_bp'
qgoal_node_mem_free_bp = 'node_mem_free_bp'
qgoal_metrics = [qgoal_user_input, qgoal_some_mem_psi_us,
                 qgoal_node_mem_used_bp, qgoal_node_mem_free_bp]

class DamosQuotaGoal:
    metric = None
    target_value = None
    current_value = None
    nid = None
    quotas = None

    def __init__(self, metric=qgoal_user_input,
                 target_value='0', current_value='0', nid=None):
        if not metric in qgoal_metrics:
            raise Exception('unsupported DAMOS quota goal metric')
        self.metric = metric
        if metric == qgoal_some_mem_psi_us:
            self.target_value = _damo_fmt_str.text_to_us(target_value)
        elif metric in [qgoal_node_mem_used_bp, qgoal_node_mem_free_bp]:
            self.target_value = _damo_fmt_str.text_to_bp(target_value)
        else:
            self.target_value = _damo_fmt_str.text_to_nr(target_value)
        self.current_value = _damo_fmt_str.text_to_nr(current_value)
        if nid is None:
            self.nid = None
        else:
            self.nid = _damo_fmt_str.text_to_nr(nid)

    @classmethod
    def metric_require_nid(cls, metric):
        return metric in [qgoal_node_mem_used_bp, qgoal_node_mem_free_bp]

    def has_nid(self):
        return DamosQuotaGoal.metric_require_nid(self.metric)

    def to_str(self, raw):
        metric_str = self.metric
        if self.has_nid():
            metric_str = '%s (nid %s)' % (
                    metric_str, _damo_fmt_str.format_nr(self.nid, raw))
        return 'metric %s target %s current %s' % (
                metric_str,
                _damo_fmt_str.format_nr(self.target_value, raw),
                _damo_fmt_str.format_nr(self.current_value, raw),)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return (type(self) == type(other) and self.metric == other.metric and
                self.nid == other.nid and
                self.target_value == other.target_value and
                self.current_value == other.current_value)

    @classmethod
    def from_kvpairs(cls, kv):
        if 'target_value_bp' in kv:
            # For supporting old version of bad naming.  Should deprecate
            # later.
            return DamosQuotaGoal(target_value=kv['target_value_bp'],
                                  current_value=kv['current_value_bp'])
        return DamosQuotaGoal(
                metric=kv['metric'], nid=kv['nid'] if 'nid' in kv else None,
                target_value=kv['target_value'],
                current_value=kv['current_value'])

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('metric', self.metric),
            ('nid', _damo_fmt_str.format_nr(self.nid, raw)
             if self.nid is not None else None),
            ('target_value', _damo_fmt_str.format_nr(self.target_value,
                raw)),
            ('current_value', _damo_fmt_str.format_nr(self.current_value,
                raw))])

class DamosQuotas:
    time_ms = None
    sz_bytes = None
    reset_interval_ms = None
    weight_sz_permil = None
    weight_nr_accesses_permil = None
    weight_age_permil = None
    goals = None
    effective_sz_bytes = None
    scheme = None

    def __init__(self, time_ms=0, sz_bytes=0, reset_interval_ms='max',
            weights=['0 %', '0 %', '0 %'], goals=[], effective_sz_bytes=0):
        self.time_ms = _damo_fmt_str.text_to_ms(time_ms)
        self.sz_bytes = _damo_fmt_str.text_to_bytes(sz_bytes)
        self.reset_interval_ms = _damo_fmt_str.text_to_ms(reset_interval_ms)
        self.weight_sz_permil = _damo_fmt_str.text_to_permil(weights[0])
        self.weight_nr_accesses_permil = _damo_fmt_str.text_to_permil(
                weights[1])
        self.weight_age_permil = _damo_fmt_str.text_to_permil(weights[2])
        self.goals = goals
        self.effective_sz_bytes = _damo_fmt_str.text_to_bytes(
                effective_sz_bytes)
        for goal in self.goals:
            goal.quotas = self

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return (type(self) == type(other) and self.time_ms == other.time_ms and
                self.sz_bytes == other.sz_bytes and self.reset_interval_ms ==
                other.reset_interval_ms and self.weight_sz_permil ==
                other.weight_sz_permil and self.weight_nr_accesses_permil ==
                other.weight_nr_accesses_permil and self.weight_age_permil ==
                other.weight_age_permil and self.goals == other.goals)

    @classmethod
    def from_kvpairs(cls, kv):
        if 'goals' in kv:
            goals = [DamosQuotaGoal.from_kvpairs(goal) for goal in kv['goals']]
        else:
            goals = []
        return DamosQuotas(kv['time_ms'], kv['sz_bytes'],
                kv['reset_interval_ms'],
                [kv['weights']['sz_permil'],
                    kv['weights']['nr_accesses_permil'],
                    kv['weights']['age_permil'],],
                goals,
                kv['effective_sz_bytes'] if 'effective_sz_bytes' in kv else 0)

    def to_str(self, raw, params_only=False):
        if params_only is False:
            lines = [
                '%s / %s / %s per %s' % (
                    _damo_fmt_str.format_time_ns(self.time_ms * 1000000, raw),
                    _damo_fmt_str.format_sz(self.sz_bytes, raw),
                    _damo_fmt_str.format_sz(self.effective_sz_bytes, raw),
                    _damo_fmt_str.format_time_ms(self.reset_interval_ms, raw))]
        else:
            lines = [
                '%s / %s per %s' % (
                    _damo_fmt_str.format_time_ns(self.time_ms * 1000000, raw),
                    _damo_fmt_str.format_sz(self.sz_bytes, raw),
                    _damo_fmt_str.format_time_ms(self.reset_interval_ms, raw))]

        for idx, goal in enumerate(self.goals):
            lines.append('goal %d: %s' % (idx, goal.to_str(raw)))
        lines.append(
            'priority: sz %s, nr_accesses %s, age %s' % (
                _damo_fmt_str.format_permil(self.weight_sz_permil, raw),
                _damo_fmt_str.format_permil(
                    self.weight_nr_accesses_permil, raw),
                _damo_fmt_str.format_permil(self.weight_age_permil, raw)))
        return '\n'.join(lines)

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('time_ms', _damo_fmt_str.format_time_ms_exact(self.time_ms, raw)),
            ('sz_bytes', _damo_fmt_str.format_sz(self.sz_bytes, raw)),
            ('reset_interval_ms', _damo_fmt_str.format_time_ms_exact(
                self.reset_interval_ms, raw)),
            ('goals', [goal.to_kvpairs(raw) for goal in self.goals]),
            ('effective_sz_bytes',
             _damo_fmt_str.format_sz(self.effective_sz_bytes, raw)),
            ('weights', (collections.OrderedDict([
                ('sz_permil',
                    _damo_fmt_str.format_permil(self.weight_sz_permil, raw)),
                ('nr_accesses_permil', _damo_fmt_str.format_permil(
                    self.weight_nr_accesses_permil, raw)),
                ('age_permil',
                    _damo_fmt_str.format_permil(self.weight_age_permil, raw))])
                ))])

damos_wmarks_metric_none = 'none'
damos_wmarks_metric_free_mem_rate = 'free_mem_rate'

class DamosWatermarks:
    metric = None
    interval_us = None
    high_permil = None
    mid_permil = None
    low_permil = None

    # no limit by default
    def __init__(self, metric=damos_wmarks_metric_none, interval_us=0,
            high='0 %', mid='0 %', low='0 %'):
        # 'none' or 'free_mem_rate'
        if not metric in [damos_wmarks_metric_none,
                damos_wmarks_metric_free_mem_rate]:
            raise Exception('wrong watermark metric (%s)' % metric)
        self.metric = metric
        self.interval_us = _damo_fmt_str.text_to_us(interval_us)
        self.high_permil = _damo_fmt_str.text_to_permil(high)
        self.mid_permil = _damo_fmt_str.text_to_permil(mid)
        self.low_permil = _damo_fmt_str.text_to_permil(low)

    def to_str(self, raw):
        return '\n'.join([
            'metric %s, interval %s' % (self.metric,
                _damo_fmt_str.format_time_us(self.interval_us, raw)),
            '%s, %s, %s' % (
                _damo_fmt_str.format_permil(self.high_permil, raw),
                _damo_fmt_str.format_permil(self.mid_permil, raw),
                _damo_fmt_str.format_permil(self.low_permil, raw)),
            ])

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return (type(self) == type(other) and self.metric == other.metric and
                self.interval_us == other.interval_us and
                self.high_permil == other.high_permil and
                self.mid_permil == other.mid_permil and
                self.low_permil == other.low_permil)

    @classmethod
    def from_kvpairs(cls, kv):
        return DamosWatermarks(*[kv[x] for x in
            ['metric', 'interval_us', 'high_permil', 'mid_permil',
                'low_permil']])

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
                ('metric', self.metric),
                ('interval_us', _damo_fmt_str.format_time_us_exact(
                    self.interval_us, raw)),
                ('high_permil',
                    _damo_fmt_str.format_permil(self.high_permil, raw)),
                ('mid_permil',
                    _damo_fmt_str.format_permil(self.mid_permil, raw)),
                ('low_permil',
                    _damo_fmt_str.format_permil(self.low_permil, raw)),
                ])

class DamosFilter:
    filter_type = None  # anon, memcg, young, hugepage_size, unmapped, addr, or
                        # target
    matching = None
    allow = None
    memcg_path = None
    address_range = None    # DamonRegion
    hugepage_size = None    # hugepage size in bytes
    damon_target_idx = None
    scheme = None

    def __init__(self, filter_type, matching, allow=False,
                 memcg_path=None, address_range=None, damon_target_idx=None,
                 hugepage_size=None):
        self.filter_type = filter_type
        self.matching = _damo_fmt_str.text_to_bool(matching)
        self.memcg_path = memcg_path
        self.allow = _damo_fmt_str.text_to_bool(allow)
        self.address_range = address_range
        self.hugepage_size = hugepage_size
        if damon_target_idx != None:
            self.damon_target_idx = _damo_fmt_str.text_to_nr(damon_target_idx)

    def to_str(self, raw):
        words = []
        if self.allow:
            words.append('allow')
        else:
            words.append('reject')
        if self.matching is False:
            words.append('none')
        words.append(self.filter_type)
        if self.filter_type in ['anon', 'young', 'unmapped']:
            return ' '.join(words)
        if self.filter_type == 'memcg':
            return ' '.join(words + [self.memcg_path])
        if self.filter_type == 'addr':
            return ' '.join(words + [self.address_range.to_str(raw)])
        if self.filter_type == 'target':
            return ' '.join(words + [_damo_fmt_str.format_nr(
                    self.damon_target_idx, raw)])
        if self.filter_type == 'hugepage_size':
            return ' '.join(words + [self.hugepage_size.to_str(raw)])

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    @classmethod
    def from_kvpairs(cls, kv):
        allow = False
        if 'allow' in kv:
            allow = kv['allow']
        # filter_pass has renamed to allow
        elif 'filter_pass' in kv:
            allow = kv['filter_pass']
        return DamosFilter(
                kv['filter_type'], kv['matching'],
                allow,
                kv['memcg_path'] if kv['filter_type'] == 'memcg' else '',
                DamonRegion.from_kvpairs(kv['address_range'])
                    if kv['filter_type'] == 'addr' else None,
                kv['damon_target_idx']
                    if kv['filter_type'] == 'target' else None)

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('filter_type', self.filter_type),
            ('matching', self.matching),
            ('allow', self.allow),
            ('memcg_path', self.memcg_path),
            ('address_range', self.address_range.to_kvpairs(raw) if
                self.address_range != None else None),
            ('damon_target_idx',
                _damo_fmt_str.format_nr(self.damon_target_idx, raw)
                if self.damon_target_idx != None else None)])

    def handled_by_ops(self):
        # whether this filter is handled by DAMON operations set layer
        return self.filter_type in ['anon', 'memcg', 'young', 'hugepage_size',
                                    'unmapped']

class DamosStats:
    nr_tried = None
    sz_tried = None
    nr_applied = None
    sz_applied = None
    sz_ops_filter_passed = None
    qt_exceeds = None

    def __init__(self, nr_tried=0, sz_tried=0, nr_applied=0, sz_applied=0,
                 sz_ops_filter_passed=0, qt_exceeds=0):
        self.nr_tried = _damo_fmt_str.text_to_nr(nr_tried)
        self.sz_tried = _damo_fmt_str.text_to_bytes(sz_tried)
        self.nr_applied = _damo_fmt_str.text_to_nr(nr_applied)
        self.sz_applied = _damo_fmt_str.text_to_bytes(sz_applied)
        self.sz_ops_filter_passed = _damo_fmt_str.text_to_bytes(
                sz_ops_filter_passed)
        self.qt_exceeds = _damo_fmt_str.text_to_nr(qt_exceeds)

    def to_str(self, raw):
        return '\n'.join([
            'tried %s times (%s)' % (
                _damo_fmt_str.format_nr(self.nr_tried, raw),
                _damo_fmt_str.format_sz(self.sz_tried, raw)),
            'applied %s times (%s)' % (
                _damo_fmt_str.format_nr(self.nr_applied, raw),
                _damo_fmt_str.format_sz(self.sz_applied, raw)),
            '%s passed filters' %
            _damo_fmt_str.format_sz(self.sz_ops_filter_passed, raw),
            'quota exceeded %d times' % self.qt_exceeds,
            ])

    def __str__(self):
        return self.to_str(False)

    def to_kvpairs(self, raw=False):
        kv = collections.OrderedDict()
        kv['nr_tried'] = _damo_fmt_str.format_nr(self.nr_tried, raw)
        kv['sz_tried'] = _damo_fmt_str.format_sz(self.sz_tried, raw)
        kv['nr_applied'] = _damo_fmt_str.format_nr(self.nr_applied, raw)
        kv['sz_applied'] = _damo_fmt_str.format_sz(self.sz_applied, raw)
        kv['sz_ops_filter_passed'] = _damo_fmt_str.format_sz(
                self.sz_ops_filter_passed, raw)
        kv['qt_exceeds'] = _damo_fmt_str.format_nr(self.qt_exceeds, raw)
        return kv

    @classmethod
    def from_kvpairs(cls, kv):
        return cls(kv['nr_tried'], kv['sz_tried'],
                   kv['nr_applied'], kv['sz_applied'],
                   kv['sz_ops_filter_passed'], kv['qt_exceeds'])

# TODO: check support of pageout and lru_(de)prio
damos_actions = [
        'willneed',
        'cold',
        'pageout',
        'hugepage',
        'nohugepage',
        'lru_prio',
        'lru_deprio',
        'migrate_hot',
        'migrate_cold',
        'stat',
        ]

damos_action_willneed = damos_actions[0]
damos_action_cold = damos_actions[1]
damos_action_pageout = damos_actions[2]
damos_action_hugepage = damos_actions[3]
damos_action_nohugepage = damos_actions[4]
damos_action_lru_prio = damos_actions[5]
damos_action_lru_deprio = damos_actions[6]
damos_action_migrate_hot = damos_actions[7]
damos_action_migrate_cold = damos_actions[8]
damos_action_stat = damos_actions[9]

def is_damos_migrate_action(action):
    if action == damos_action_migrate_hot or \
       action == damos_action_migrate_cold:
        return True
    return False

class Damos:
    access_pattern = None
    action = None
    target_nid = None
    apply_interval_us = None
    quotas = None
    watermarks = None
    filters = None
    stats = None
    tried_regions = None
    tried_bytes = None
    context = None


    # for monitoring only by default
    def __init__(
            self, access_pattern=None,
            action=damos_action_stat, target_nid=None, apply_interval_us=None,
            quotas=None, watermarks=None, filters=None, stats=None,
            tried_regions=None, tried_bytes=None):
        self.access_pattern = (access_pattern
                if access_pattern != None else DamosAccessPattern())
        if not action in damos_actions:
            raise Exception('wrong damos action: %s' % action)
        self.action = action
        self.target_nid = target_nid
        if apply_interval_us != None:
            self.apply_interval_us = _damo_fmt_str.text_to_us(
                    apply_interval_us)
        else:
            self.apply_interval_us = 0
        self.quotas = quotas if quotas != None else DamosQuotas()
        self.quotas.scheme = self
        self.watermarks = (watermarks
                if watermarks != None else DamosWatermarks())
        self.filters = filters if filters != None else []
        for filter_ in self.filters:
            filter_.scheme = self
        self.stats = stats if stats != None else DamosStats()
        self.tried_regions = tried_regions if tried_regions != None else []
        for tried_region in self.tried_regions:
            tried_region.scheme = self
        self.tried_bytes = 0
        if tried_bytes:
            self.tried_bytes = _damo_fmt_str.text_to_bytes(
                    tried_bytes)
        else:
            for region in self.tried_regions:
                self.tried_bytes += region.size()

    def str_action_line(self, raw):
        action_words = ['action: %s' % self.action]
        if is_damos_migrate_action(self.action):
            action_words.append('to node %s' % self.target_nid)
        action_words.append('per %s' %
            _damo_fmt_str.format_time_us(self.apply_interval_us, raw)
            if self.apply_interval_us != 0 else 'per aggr interval')
        return ' '.join(action_words)

    def to_str(self, raw, params_only=False):
        lines = [self.str_action_line(raw)]
        if self.access_pattern is not None:
            lines.append('target access pattern')
            lines.append(_damo_fmt_str.indent_lines(
                self.access_pattern.to_str(raw), 4))
        if self.quotas is not None:
            lines.append('quotas')
            lines.append(_damo_fmt_str.indent_lines(
                self.quotas.to_str(raw, params_only), 4))
        if self.watermarks is not None:
            lines.append('watermarks')
            lines.append(_damo_fmt_str.indent_lines(
                self.watermarks.to_str(raw), 4))
        for idx, damos_filter in enumerate(self.filters):
            lines.append('filter %d' % idx)
            lines.append(_damo_fmt_str.indent_lines(
                damos_filter.to_str(raw), 4))
        if params_only is False and self.stats is not None:
            lines.append('statistics')
            lines.append(_damo_fmt_str.indent_lines(self.stats.to_str(raw), 4))
        if params_only is False and self.tried_regions is not None:
            lines.append('tried regions (%s)' % _damo_fmt_str.format_sz(
                    self.tried_bytes, raw))
            for region in self.tried_regions:
                lines.append(_damo_fmt_str.indent_lines(region.to_str(raw), 4))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.access_pattern == other.access_pattern and
                self.action == other.action and
                self.apply_interval_us == other.apply_interval_us and
                self.quotas == other.quotas and
                self.watermarks == other.watermarks and
                self.filters == other.filters)

    @classmethod
    def from_kvpairs(cls, kv):
        filters = []
        if 'filters' in kv:
            for damos_filter_kv in kv['filters']:
                filters.append(DamosFilter.from_kvpairs(damos_filter_kv))
        return Damos(DamosAccessPattern.from_kvpairs(kv['access_pattern'])
                    if 'access_pattern' in kv else DamosAccessPattern(),
                kv['action'] if 'action' in kv else damos_action_stat,
                kv['target_nid'] if 'target_nid' in kv else None,
                kv['apply_interval_us'] if 'apply_interval_us' in kv else None,
                DamosQuotas.from_kvpairs(kv['quotas'])
                    if 'quotas' in kv else DamosQuotas(),
                DamosWatermarks.from_kvpairs(kv['watermarks'])
                    if 'watermarks' in kv else DamosWatermarks(),
                filters,
                None, None)

    def to_kvpairs(self, raw=False, omit_defaults=False, params_only=False):
        kv = collections.OrderedDict()
        kv['action'] = self.action
        if is_damos_migrate_action(self.action):
            kv['target_nid'] = self.target_nid
        if not omit_defaults or self.access_pattern != DamosAccessPattern():
            kv['access_pattern'] = self.access_pattern.to_kvpairs(raw)
        kv['apply_interval_us'] = self.apply_interval_us
        if not omit_defaults or self.quotas != DamosQuotas():
            kv['quotas'] = self.quotas.to_kvpairs(raw)
        if not omit_defaults or self.watermarks != DamosWatermarks():
            kv['watermarks'] = self.watermarks.to_kvpairs(raw)
        if not omit_defaults or self.filters != []:
            filters = []
            for damos_filter in self.filters:
                filters.append(damos_filter.to_kvpairs(raw))
            kv['filters'] = filters
        if not params_only and self.stats is not None:
            kv['stats'] = self.stats.to_kvpairs(raw)
        return kv

    def effectively_equal(self, other, intervals):
        return (type(self) == type(other) and
                self.access_pattern.effectively_equal(
                    other.access_pattern, intervals) and
                self.action == other.action and
                self.apply_interval_us == other.apply_interval_us and
                self.quotas == other.quotas and
                self.watermarks == other.watermarks and
                self.filters == other.filters)

class DamonCtx:
    ops = None
    targets = None
    intervals = None
    nr_regions = None
    schemes = None
    kdamond = None

    def __init__(self, ops='paddr', targets=None, intervals=None,
                 nr_regions=None, schemes=None):
        self.ops = ops
        self.targets = targets if targets is not None else []
        for target in self.targets:
            target.context = self
        self.intervals = (intervals
                          if intervals is not None else DamonIntervals())
        self.nr_regions = (nr_regions if nr_regions is not None
                           else DamonNrRegionsRange())
        self.schemes = schemes if schemes is not None else Damos()
        for scheme in self.schemes:
            scheme.context = self

    def to_str(self, raw, params_only=False):
        lines = ['ops: %s' % self.ops]
        for idx, target in enumerate(self.targets):
            lines.append('target %d' % idx)
            lines.append(_damo_fmt_str.indent_lines(target.to_str(raw), 4))
        intervals_lines = self.intervals.to_str(raw).split('\n')
        if len(intervals_lines) == 1:
            lines.append('intervals: %s' % intervals_lines[0])
        else:
            lines.append('intervals')
            lines.append(
                    _damo_fmt_str.indent_lines(self.intervals.to_str(raw), 4))
        lines.append('nr_regions: %s' % self.nr_regions.to_str(raw))
        for idx, scheme in enumerate(self.schemes):
            lines.append('scheme %d' % idx)
            lines.append(_damo_fmt_str.indent_lines(
                scheme.to_str(raw, params_only), 4))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    def __hash__(self):
        return hash(self.__str__())

    @classmethod
    def from_kvpairs(cls, kv):
        ctx = DamonCtx(
                kv['ops'],
                [DamonTarget.from_kvpairs(t) for t in kv['targets']],
                DamonIntervals.from_kvpairs(kv['intervals'])
                    if 'intervals' in kv else DamonIntervals(),
                DamonNrRegionsRange.from_kvpairs(kv['nr_regions'])
                    if 'nr_regions' in kv else DAmonNrRegionsRange(),
                [Damos.from_kvpairs(s) for s in kv['schemes']]
                    if 'schemes' in kv else [])
        return ctx

    def to_kvpairs(self, raw=False, omit_defaults=False, params_only=False):
        kv = collections.OrderedDict({})
        kv['ops'] = self.ops
        kv['targets'] = [t.to_kvpairs(raw) for t in self.targets]
        if not omit_defaults or self.intervals != DamonIntervals():
            kv['intervals'] = self.intervals.to_kvpairs(raw)
        if not omit_defaults or self.nr_regions != DamonNrRegionsRange():
            kv['nr_regions'] = self.nr_regions.to_kvpairs(raw)
        kv['schemes'] = [s.to_kvpairs(raw, omit_defaults, params_only)
                         for s in self.schemes]
        return kv

def target_has_pid(ops):
    return ops in ['vaddr', 'fvaddr']

class Kdamond:
    state = None
    pid = None
    contexts = None

    def __init__(self, state, pid, contexts):
        self.state = state
        self.pid = pid
        self.contexts = contexts
        for ctx in self.contexts:
            ctx.kdamond = self

    def summary_str(self, show_cpu=False, params_only=False,
                    omit_defaults=False):
        words = []
        if params_only is False and self.state is not None:
            words.append('state: %s' % self.state)
        if params_only is False and self.pid is not None:
            words.append('pid: %s' % self.pid)
        if show_cpu:
            words.append('cpu usage: %s' % self.get_cpu_usage())
        return ', '.join(words)

    def to_str(self, raw, show_cpu=False, params_only=False):
        lines = []
        summary_line = self.summary_str(show_cpu, params_only)
        if summary_line != '':
            lines.append(summary_line)
        for idx, ctx in enumerate(self.contexts):
            lines.append('context %d' % idx)
            lines.append(_damo_fmt_str.indent_lines(
                ctx.to_str(raw, params_only), 4))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(False)

    def __eq__(self, other):
        return type(self) == type(other) and '%s' % self == '%s' % other

    def __hash__(self):
        return hash(self.__str__())

    def get_cpu_usage(self):
        if self.state == "off":
            return "0.0"
        try:
            res = subprocess.check_output(['ps', '-p', self.pid, '-o', '%cpu'], text=True)
            return res.split("\n")[1].strip()
        except:
            return 'error'

    @classmethod
    def from_kvpairs(cls, kv):
        return Kdamond(
                kv['state'] if 'state' in kv else 'off',
                kv['pid'] if 'pid' in kv else None,
                [DamonCtx.from_kvpairs(c) for c in kv['contexts']])

    def to_kvpairs(self, raw=False, omit_defaults=False, params_only=False):
        kv = collections.OrderedDict()
        if not params_only:
            kv['state'] = self.state
            kv['pid'] = self.pid
        kv['contexts'] = [c.to_kvpairs(raw, omit_defaults, params_only)
                          for c in self.contexts]
        return kv

import _damo_fs
import _damon_dbgfs
import _damon_sysfs
import damo_version

# System check

# damo supports all DAMON-enabled kernels.  For that, damo maintains list of
# the DAMON features, and a dict saying whether the feature is supported on the
# running kernel.  Since the supports depend on underlying DAMON interface, the
# dict is populated by _damon_fs, and saved as _damon_fs.feature_supports.
#
# The feature_supports population cannot be fully done while DAMON is running,
# particularly in case of debugfs.  Specifically, it has to do writing some
# values to some files and check if it success or fails.  While DAMON is
# running, such writing may always fail (-EBUSY).  Sysfs is ok for now since it
# allows writing files while DAMON is running, except 'state' file.  But,
# similar issue could happen in future.
#
# Hence, damo features for online DAMON control or snapshot cannot make
# feature_supprots correctly.  And repeated feature check is waste of time,
# anyway.
#
# To work around, ask features that would run while DAMON is not running to
# build the feature_supports dict, and write on feature_supports_file_path
# file.  If the file already exists and valid, other damo features that depends
# on feature_supports setup feature_supports dict by reading it from the file.
# Specifically, ensure_initialized() receives the save/load request as
# arguments.

features = ['record',       # was in DAMON patchset, but not merged in mainline
            'vaddr',        # merged in v5.15, thebeginning
            'schemes',      # merged in v5.16
            'init_regions', # merged in v5.16 (90bebce9fcd6)
            'paddr',        # merged in v5.16 (a28397beb55b)
            'schemes_speed_limit',      # merged in v5.16 (2b8a248d5873)
            'schemes_quotas',           # merged in v5.16 (1cd243030059)
            'schemes_prioritization',   # merged in v5.16 (38683e003153)
            'schemes_wmarks',           # merged in v5.16 (ee801b7dd782)
            'schemes_stat_succ',        # merged in v5.17 (0e92c2ee9f45)
            'schemes_stat_qt_exceed',   # merged in v5.17 (0e92c2ee9f45)
            'init_regions_target_idx',  # merged in v5.18 (144760f8e0c3)
            'fvaddr',       # merged in v5.19 (b82434471cd2)
            'schemes_tried_regions',    # merged in v6.2-rc1
            'schemes_filters',          # merged in v6.3-rc1
            'schemes_filters_anon',     # merged in v6.3-rc1
            'schemes_filters_memcg',    # merged in v6.3-rc1
            'schemes_tried_regions_sz', # merged in v6.6-rc1
            'schemes_filters_addr',     # merged in v6.6-rc1
            'schemes_filters_target',   # merged in v6.6-rc1
            'schemes_apply_interval',   # merged in v6.7-rc1
            'schemes_quota_goals',      # merged in v6.8-rc1
            'schemes_quota_effective_bytes',    # merged in v6.9-rc1
            'schemes_quota_goal_metric',    # merged in v6.9-rc1
            'schemes_quota_goal_some_psi',  # merged in v6.9-rc1
            'schemes_filters_young',    # merged in v6.10-rc1
            'schemes_migrate',          # merged in v6.11-rc1
            'sz_ops_filter_passed',     # merged in v6.14-rc1
            'allow_filter',             # merged in v6.14-rc1
            'schemes_filters_hugepage_size',
                                        # merged in mm-unstable
            'schemes_filters_unmapped', # merged in mm-unstable
            'intervals_goal',           # merged in mm-unstable
            'schemes_filters_core_ops_dirs',
                                        # merged in mm-unstable
            'schemes_quota_goal_node_mem_used_free',
                                        # under development
            ]

_damon_fs = None

def ensure_root_permission():
    if os.geteuid() != 0:
        print('Run as root')
        exit(1)

feature_supports_file_path = os.path.join(os.environ['HOME'],
        '.damo.damon_feature_supports')

# initial version is json format of feature_supports dict.  the version doesn't
# have file format version at all.
#
# Format version 1 file contains feature_supports for debugfs and sysfs, and
# the version field.
#
# Format version 2 file contains the version of the kernel that
# feature_supports is made on.
#
# Format version 3 file contains the version of damo.
feature_support_file_format_ver = 3

def version_mismatch(feature_supports):
    if not 'file_format_ver' in feature_supports:
        file_format_ver = 0
    else:
        file_format_ver = feature_supports['file_format_ver']
    if file_format_ver != feature_support_file_format_ver:
        return 'unsupported format version %s' % file_format_ver
    kernel_ver = feature_supports['kernel_version']
    current_kernel_ver = subprocess.check_output(['uname', '-r']).decode()
    if kernel_ver != current_kernel_ver:
        return 'kernel is different from that created %s (%s != %s)' % (
                feature_supports_file_path, kernel_ver, current_kernel_ver)
    damo_ver = feature_supports['damo_version']
    if damo_ver != damo_version.__version__:
        return 'damo version is different from that created %s (%s != %s)' % (
                feature_supports_file_path, damo_ver, damo_version.__version__)
    return None

def read_feature_supports_file():
    '''Return error string'''
    if not os.path.isfile(feature_supports_file_path):
        return '%s not exist' % feature_supports_file_path
    try:
        with open(feature_supports_file_path, 'r') as f:
            feature_supports = json.load(f)
    except Exception as e:
        return 'reading feature supports failed (%s)' % e

    err = version_mismatch(feature_supports)
    if err is not None:
        return err

    if not damon_interface() in feature_supports:
        return 'no feature_supports for %s interface saved' % damon_interface()
    return set_feature_supports(feature_supports[damon_interface()])

def write_feature_supports_file():
    '''Return error string'''
    feature_supports, err = get_feature_supports()
    if err != None:
        return 'get_feature_supports() failed (%s)' % err

    to_save = {}
    # if feature supports file has the information for file system that
    # different from the one current execution is using, keep it.
    if os.path.isfile(feature_supports_file_path):
        with open(feature_supports_file_path, 'r') as f:
            try:
                to_save = json.load(f)
            except:
                # Maybe previous writing was something wrong.  Just overwrite.
                to_save = {}
        # if it is written by old version of damo, discard previously written
        # things.
        if version_mismatch(to_save) is not None:
            to_save = {}

    to_save['file_format_ver'] = feature_support_file_format_ver
    to_save['kernel_version'] = subprocess.check_output(
            ['uname', '-r']).decode()
    to_save['damo_version'] = damo_version.__version__
    to_save[damon_interface()] = feature_supports

    with open(feature_supports_file_path, 'w') as f:
        json.dump(to_save, f, indent=4, sort_keys=True)

def feature_supported(feature):
    return _damon_fs.feature_supported(feature)

def get_feature_supports():
    err = _damon_fs.update_supported_features()
    if err != None:
        return None, err
    return _damon_fs.feature_supports, None

def set_feature_supports(feature_supports):
    if sorted(features) != sorted(feature_supports.keys()):
        # The feature_supports_file is old.  E.g., The file has written by old
        # version of damo, and then being read by new version.
        # e.g., https://github.com/awslabs/damo/issues/103
        return 'feature supports file is not updated'

    _damon_fs.feature_supports = feature_supports
    return None

def set_damon_interface(damon_interface):
    global _damon_fs
    if damon_interface == 'sysfs':
        _damon_fs = _damon_sysfs
    elif damon_interface == 'debugfs':
        _damon_fs = _damon_dbgfs
    elif damon_interface == 'auto':
        if _damon_sysfs.supported():
            _damon_fs = _damon_sysfs
        else:
            _damon_fs = _damon_dbgfs
    if not _damon_fs.supported():
        return 'DAMON interface (%s) not supported' % damon_interface
    return None

def initialize(damon_interface, debug_damon, is_stop):
    err = set_damon_interface(damon_interface)
    if err is not None:
        return err

    if debug_damon:
        _damo_fs.debug_print_ops(True)

    # try reading previously saved feature_supports file, to avoid unnecessary
    # feature check I/O
    err = read_feature_supports_file()
    if err is None:
        return err

    # stop would be called while DAMON is running.  It can success without
    # knowing features.  Just proceed.
    if is_stop:
        return None

    # While DAMON is running, feature checking I/O can fail, corrupt something,
    # or make something complicated.
    if any_kdamond_running():
        return 'feature_supports loading failed (%s), and DAMON is running'

    return write_feature_supports_file()

initialized = False
def ensure_initialized(args, is_stop):
    global initialized

    if initialized:
        return
    err = initialize(args.damon_interface_DEPRECATED, args.debug_damon,
                     is_stop)
    if err != None:
        print(err)
        exit(1)
    initialized = True

def ensure_root_and_initialized(args, is_stop=False):
    ensure_root_permission()
    ensure_initialized(args, is_stop)

def damon_interface():
    if _damon_fs == _damon_sysfs:
        return 'sysfs'
    elif _damon_fs == _damon_dbgfs:
        return 'debugfs'
    raise Exception('_damo_fs is neither _damon_sysfs nor _damon_dbgfs')

# DAMON control

def stage_kdamonds(kdamonds):
    return _damon_fs.stage_kdamonds(kdamonds)

def commit_staged(kdamond_idxs):
    if _damon_fs == _damon_dbgfs:
        return 'debugfs interface does not support commit_staged()'
    return _damon_fs.commit_staged(kdamond_idxs)

def commit_quota_goals(kdamond_idxs):
    if _damon_fs == _damon_dbgfs:
        return 'debugfs interface does not support commit_quota_goals()'
    return _damon_fs.commit_quota_goals(kdamond_idxs)

def commit(kdamonds, commit_quota_goals_only=False):
    if not commit_quota_goals_only:
        err = stage_kdamonds(kdamonds)
        if err:
            return 'staging updates failed (%s)' % err

    kdamond_idxs = ['%s' % idx for idx, k in enumerate(kdamonds)]

    if commit_quota_goals_only:
        err = commit_quota_goals(kdamond_idxs)
        if err:
            return 'commit quotas failed (%s)' % err
        return None

    err = commit_staged(kdamond_idxs)
    if err:
        return 'commit staged updates filed (%s)' % err
    return None

def update_tuned_intervals(kdamond_idxs=None):
    if kdamond_idxs is None:
        kdamond_idxs = running_kdamond_idxs()
    if _damon_fs == _damon_dbgfs:
        return None
    err = _damon_fs.update_tuned_intervals(kdamond_idxs)
    # 'Invalid argument' means the feature is not supported on the kernel
    if err is not None and not 'Invalid argument' in err:
        return err
    return None

def update_schemes_stats(kdamond_idxs=None):
    if kdamond_idxs == None:
        kdamond_idxs = running_kdamond_idxs()
    return _damon_fs.update_schemes_stats(kdamond_idxs)

def update_schemes_tried_bytes(kdamond_idxs=None):
    if kdamond_idxs == None:
        kdamond_idxs = running_kdamond_idxs()
    return _damon_fs.update_schemes_tried_bytes(kdamond_idxs)

def update_schemes_tried_regions(kdamond_idxs=None):
    if kdamond_idxs == None:
        kdamond_idxs = running_kdamond_idxs()
    return _damon_fs.update_schemes_tried_regions(kdamond_idxs)

def update_schemes_quota_effective_bytes(kdamond_idxs=None):
    if kdamond_idxs == None:
        kdamond_idxs = running_kdamond_idxs()
    return _damon_fs.update_schemes_quota_effective_bytes(kdamond_idxs)

def update_schemes_status(stats=True, tried_regions=True,
                          quota_effective_bytes=False):
    '''Returns error string or None'''
    schemes_exist = False
    for kdamond in current_kdamonds():
        for ctx in kdamond.contexts:
            if len(ctx.schemes) > 0:
                schemes_exist = True
                break
        if schemes_exist is True:
            break
    if schemes_exist is False:
        return None

    idxs = running_kdamond_idxs()
    if len(idxs) == 0:
        return None
    if stats:
        err = update_schemes_stats(idxs)
        if err != None:
            return err
    if tried_regions and feature_supported('schemes_tried_regions'):
        err = update_schemes_tried_regions(idxs)
        if err != None:
            return err

    if quota_effective_bytes and feature_supported('schemes_quota_effective_bytes'):
        return update_schemes_quota_effective_bytes(idxs)

    return None

def turn_damon_on(kdamonds_idxs):
    err = _damon_fs.turn_damon_on(kdamonds_idxs)
    if err:
        return err
    wait_kdamonds_turned_on()

def turn_damon_off(kdamonds_idxs):
    err = _damon_fs.turn_damon_off(kdamonds_idxs)
    if err:
        return err
    wait_kdamonds_turned_off()

# DAMON status reading

def is_kdamond_running(kdamond_idx):
    return _damon_fs.is_kdamond_running(kdamond_idx)

def current_kdamonds():
    return _damon_fs.current_kdamonds()

def update_read_kdamonds(
        nr_retries=0, update_stats=True, update_tried_regions=True,
        update_quota_effective_bytes=False, do_update_tuned_intervals=False):
    err = 'assumed error'
    nr_tries = 0
    while True:
        if do_update_tuned_intervals:
            err = update_tuned_intervals()
            if err is not None:
                nr_tries += 1
                time.sleep(
                        random.randrange(2**(nr_tries - 1), 2**nr_tries) / 100)
                continue
        err = update_schemes_status(update_stats, update_tried_regions,
                                    update_quota_effective_bytes)
        nr_tries += 1
        if err == None or nr_tries > nr_retries:
            break
        time.sleep(random.randrange(2**(nr_tries - 1), 2**nr_tries) / 100)
    if err:
        return None, err
    return current_kdamonds(), None

def nr_kdamonds():
    return _damon_fs.nr_kdamonds()

def running_kdamond_idxs():
    return [idx for idx in range(nr_kdamonds())
            if is_kdamond_running(idx)]

def any_kdamond_running():
    for idx in range(nr_kdamonds()):
        if is_kdamond_running(idx):
            return True
    return False

def wait_kdamonds_turned_on():
    for idx in range(nr_kdamonds()):
        while not is_kdamond_running(idx):
            time.sleep(1)

def wait_kdamonds_turned_off():
    for idx in range(nr_kdamonds()):
        while is_kdamond_running(idx):
            time.sleep(1)
