# SPDX-License-Identifier: GPL-2.0

import collections
import copy
import json
import os
import random
import signal
import subprocess
import time
import zlib

import _damo_fmt_str
import _damon
import damo_report_access

PERF = 'perf'
perf_event_damon_aggregated = 'damon:damon_aggregated'
perf_event_damos_before_apply = 'damon:damos_before_apply'

class DamonSnapshot:
    '''
    Contains a snapshot of data access monitoring results
    '''
    start_time = None
    end_time = None
    regions = None
    total_bytes = None

    def update_total_bytes(self):
        self.total_bytes = sum([r.size() for r in self.regions])

    def __init__(self, start_time, end_time, regions, total_bytes):
        self.start_time = start_time
        self.end_time = end_time
        self.regions = regions
        self.total_bytes = total_bytes
        if self.total_bytes is None:
            self.update_total_bytes()

    @classmethod
    def from_kvpairs(cls, kv):
        return DamonSnapshot(
                _damo_fmt_str.text_to_ns(kv['start_time']),
                _damo_fmt_str.text_to_ns(kv['end_time']),
                [_damon.DamonRegion.from_kvpairs(r) for r in kv['regions']],
                _damo_fmt_str.text_to_bytes(kv['total_bytes'])
                if 'total_bytes' in kv and kv['total_bytes'] is not None
                else None)

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('start_time', _damo_fmt_str.format_time_ns_exact(
                self.start_time, raw)),
            ('end_time', _damo_fmt_str.format_time_ns_exact(
                self.end_time, raw)),
            ('regions', [r.to_kvpairs() for r in self.regions]),
            ('total_bytes', _damo_fmt_str.format_sz(self.total_bytes, raw)
                if self.total_bytes is not None else None),
            ])

class DamonRecord:
    '''
    Contains data access monitoring results for single target
    '''
    kdamond_idx = None
    context_idx = None
    intervals = None
    scheme_idx = None
    target_id = None
    snapshots = None

    def __init__(self, kd_idx, ctx_idx, intervals, scheme_idx, target_id):
        self.kdamond_idx = kd_idx
        self.context_idx = ctx_idx
        self.intervals = intervals
        self.scheme_idx = scheme_idx
        self.target_id = target_id
        self.snapshots = []

    @classmethod
    def from_kvpairs(cls, kv):
        for keyword in ['kdamond_idx', 'context_idx', 'intervals',
                'scheme_idx']:
            if not keyword in kv:
                kv[keyword] = None

        record = DamonRecord(kv['kdamond_idx'], kv['context_idx'],
                _damon.DamonIntervals.from_kvpairs(kv['intervals'])
                if kv['intervals'] is not None else None,
                kv['scheme_idx'], kv['target_id'])
        record.snapshots = [DamonSnapshot.from_kvpairs(s)
                for s in kv['snapshots']]

        return record

    def to_kvpairs(self, raw=False):
        ordered_dict = collections.OrderedDict()
        ordered_dict['kdamond_idx'] = self.kdamond_idx
        ordered_dict['context_idx'] = self.context_idx
        ordered_dict['intervals'] = (self.intervals.to_kvpairs(raw)
                if self.intervals is not None else None)
        ordered_dict['scheme_idx'] = self.scheme_idx
        ordered_dict['target_id'] = self.target_id
        ordered_dict['snapshots'] = [s.to_kvpairs(raw) for s in self.snapshots]
        return ordered_dict

    def can_merge(self, other):
        return (
                self.kdamond_idx == other.kdamond_idx and
                self.context_idx == other.context_idx and
                self.intervals == other.intervals and
                self.scheme_idx == other.scheme_idx and
                self.target_id == other.target_id)

    def merge(self, other):
        self.snapshots += other.snapshots
        self.snapshots.sort(key=lambda s: s.start_time)

# for monitoring results manipulation

def merge_records(records):
    merged_records = []
    for record in records:
        merged = False
        for merged_record in merged_records:
            if merged_record.can_merge(record):
                merged_record.merge(record)
                merged = True
                break
        if not merged:
            merged_records.append(record)
    return merged_records

def regions_intersect(r1, r2):
    return not (r1.end <= r2.start or r2.end <= r1.start)

def add_region(regions, region, nr_acc_to_add):
    for r in regions:
        if regions_intersect(r, region):
            if not r in nr_acc_to_add:
                nr_acc_to_add[r] = 0
            nr_acc_to_add[r] = max(nr_acc_to_add[r],
                    region.nr_accesses.samples)

            new_regions = []
            if region.start < r.start:
                new_regions.append(_damon.DamonRegion(
                    region.start, r.start,
                    region.nr_accesses.samples, _damon.unit_samples,
                    region.age.aggr_intervals, _damon.unit_aggr_intervals))
            if r.end < region.end:
                new_regions.append(_damon.DamonRegion(
                        r.end, region.end,
                        region.nr_accesses.samples, _damon.unit_samples,
                        region.age.aggr_intervals,
                        _damon.unit_aggr_intervals))

            for new_r in new_regions:
                add_region(regions, new_r, nr_acc_to_add)
            return
    regions.append(region)

def aggregate_snapshots(snapshots):
    new_regions = []
    for snapshot in snapshots:
        # Suppose the first snapshot has a region 1-10:5, and the second
        # snapshot has two regions, 1-5:2, 5-10: 4.  Aggregated snapshot should
        # be 1-10:9.  That is, we should add maximum nr_accesses of
        # intersecting regions.  nr_acc_to_add contains the information.
        nr_acc_to_add = {}
        for region in snapshot.regions:
            add_region(new_regions, region, nr_acc_to_add)
        for region in nr_acc_to_add:
            region.nr_accesses.samples += nr_acc_to_add[region]
            region.nr_accesses.val = region.nr_accesses.samples
            region.nr_accesses.unit = _damon.unit_samples

    new_snapshot = DamonSnapshot(snapshots[0].start_time,
            snapshots[-1].end_time, new_regions, None)
    return new_snapshot

def adjusted_snapshots(snapshots, aggregate_interval_us):
    adjusted = []
    to_aggregate = []
    for snapshot in snapshots:
        to_aggregate.append(snapshot)
        interval_ns = to_aggregate[-1].end_time - to_aggregate[0].start_time
        if interval_ns >= aggregate_interval_us * 1000:
            adjusted.append(aggregate_snapshots(to_aggregate))
            to_aggregate = []
    return adjusted

def adjust_records(records, aggregate_interval, nr_snapshots_to_skip):
    for record in records:
        if record.intervals is not None:
            record.intervals.aggr = aggregate_interval
        record.snapshots = adjusted_snapshots(
                record.snapshots[nr_snapshots_to_skip:], aggregate_interval)

# For reading monitoring results from a file

# if number of snapshots is one and the file type is record or perf script,
# write_damon_records() adds a fake snapshot for snapshot start time deduction.
def is_fake_snapshot(snapshot):
    if len(snapshot.regions) != 1:
        return False
    r = snapshot.regions[0]
    return (r.start == 0 and r.end == 0 and
            r.nr_accesses.samples == -1 and r.age.aggr_intervals == -1)

def set_first_snapshot_start_time(records):
    for record in records:
        snapshots = record.snapshots
        if len(snapshots) < 2:
            break
        end_time = snapshots[-1].end_time
        start_time = snapshots[0].end_time
        nr_snapshots = len(snapshots) - 1
        snapshot_time = float(end_time - start_time) / nr_snapshots
        snapshots[0].start_time = snapshots[0].end_time - snapshot_time

        if is_fake_snapshot(snapshots[-1]):
            del record.snapshots[-1]

def record_of(target_id, records, intervals):
    for record in records:
        if record.target_id == target_id:
            return record
    record = DamonRecord(None, None, intervals, None, target_id)
    records.append(record)
    return record

def parse_damon_aggregated_perf_script_fields(fields):
    '''
    The line is like below:

    kdamond.0  4452 [000] 82877.315633: damon:damon_aggregated: \
            target_id=18446623435582458880 nr_regions=17 \
            140731667070976-140731668037632: 0 3

    Note that the last field is not in the early version[1].

    [1] https://lore.kernel.org/linux-mm/df8d52f1fb2f353a62ff34dc09fe99e32ca1f63f.1636610337.git.xhao@linux.alibaba.com/
    '''

    if not len(fields) in [9, 10]:
        return None, None, None, None

    end_time = int(float(fields[3][:-1]) * 1000000000)
    target_id = int(fields[5].split('=')[1])
    nr_regions = int(fields[6].split('=')[1])

    start_addr, end_addr = [int(x) for x in fields[7][:-1].split('-')]
    nr_accesses = int(fields[8])
    if len(fields) == 10:
        age = int(fields[9])
    else:
        age = None
    region = _damon.DamonRegion(start_addr, end_addr, nr_accesses,
            _damon.unit_samples, age, _damon.unit_aggr_intervals)

    return region, end_time, target_id, nr_regions

def parse_damos_before_apply_perf_script_fields(fields):
    '''
    The line is like below:

    kdamond.0  4452 [000] 82877.315633: damon:damon_aggregated: \
            target_id=18446623435582458880 nr_regions=17 \
            140731667070976-140731668037632: 0 3

    Note that the last field is not in the early version[1].

    line is like below for damos_before_apply:

    kdamond.0 47293 [000] 80801.060214: damon:damos_before_apply: \
            ctx_idx=0 scheme_idx=0 target_idx=0 nr_regions=11 \
            121932607488-135128711168: 0 136

    [1] https://lore.kernel.org/linux-mm/df8d52f1fb2f353a62ff34dc09fe99e32ca1f63f.1636610337.git.xhao@linux.alibaba.com/
    '''

    if len(fields) != 12:
        return None, None, None, None

    end_time = int(float(fields[3][:-1]) * 1000000000)
    target_id = int(fields[7].split('=')[1])
    nr_regions = int(fields[8].split('=')[1])

    start_addr, end_addr = [int(x) for x in fields[9][:-1].split('-')]
    nr_accesses = int(fields[10])
    age = int(fields[11])
    region = _damon.DamonRegion(start_addr, end_addr, nr_accesses,
            _damon.unit_samples, age, _damon.unit_aggr_intervals)

    return region, end_time, target_id, nr_regions

def parse_perf_script_line(line):
    '''
    line could be that for damon_aggregated or damos_before_apply events
    '''
    fields = line.strip().split()
    if not len(fields) > 5:
        return None, None, None, None
    traceevent = fields[4][:-1]
    if traceevent == perf_event_damon_aggregated:
        return parse_damon_aggregated_perf_script_fields(fields)
    elif traceevent == perf_event_damos_before_apply:
        return parse_damos_before_apply_perf_script_fields(fields)
    else:
        return None, None, None, None

def parse_perf_script(script_output, monitoring_intervals):
    records = []
    snapshot = None

    for line in script_output.split('\n'):
        region, end_time, target_id, nr_regions = parse_perf_script_line(line)
        if region is None:
            continue

        record = record_of(target_id, records, monitoring_intervals)
        if len(record.snapshots) == 0:
            start_time = None
        else:
            start_time = record.snapshots[-1].end_time
            if start_time > end_time:
                return None, 'trace is not time-sorted'

        if snapshot is None:
            snapshot = DamonSnapshot(start_time, end_time, [], None)
            record.snapshots.append(snapshot)
        snapshot = record.snapshots[-1]
        snapshot.regions.append(region)

        if len(snapshot.regions) == nr_regions:
            snapshot = None

    for record in records:
        for snapshot in record.snapshots:
            snapshot.update_total_bytes()

    set_first_snapshot_start_time(records)
    return records, None

def set_perf_path(perf_path):
    global PERF
    PERF = perf_path

    # Test perf record for damon event
    err = None
    try:
        subprocess.check_output(['which', PERF])
        try:
            subprocess.check_output(
                    [PERF, 'record', '-e', perf_event_damon_aggregated, '--',
                        'sleep', '0'],
                    stderr=subprocess.PIPE)
        except:
            err = 'perf record not working with "%s"' % PERF
    except:
        err = 'perf not found at "%s"' % PERF
    return err

def parse_json(json_str):
    kvpairs = json.loads(json_str)
    return [DamonRecord.from_kvpairs(kvp) for kvp in kvpairs]

def parse_compressed_json(record_file):
    with open(record_file, 'rb') as f:
        compressed = f.read()
    decompressed = zlib.decompress(compressed).decode()
    return parse_json(decompressed)

def parse_json_file(record_file):
    with open(record_file) as f:
        json_str = f.read()
    return parse_json(json_str)

def parse_records_file(record_file, monitoring_intervals=None):
    '''
    Return monitoring results records and error string
    '''

    file_type = subprocess.check_output(
            ['file', '-b', record_file]).decode().strip()
    if file_type == 'JSON data':
        try:
            return parse_json_file(record_file), None
        except Exception as e:
            return None, 'failed parsing json file (%s)' % e
    if file_type == 'zlib compressed data':
        try:
            return parse_compressed_json(record_file), None
        except Exception as e:
            return None, 'failed parsing json compressed file (%s)' % e

    perf_script_output = None
    if file_type == 'ASCII text':
        with open(record_file, 'r') as f:
            perf_script_output = f.read()
    else:
        # might be perf data
        try:
            with open(os.devnull, 'w') as fnull:
                # in some setup, perf record file ends up having no proper
                # ownership.  There's no reason to be strict about that from
                # damo.  As long as we can, just parse it with '--force'
                # option.
                perf_script_output = subprocess.check_output(
                        [PERF, 'script', '--force', '-i', record_file],
                        stderr=fnull).decode()
        except:
            # Should be record format file
            pass
    if perf_script_output is not None:
        return parse_perf_script(perf_script_output, monitoring_intervals)
    else:
        return None, 'parsing %s failed' % record_file

# for writing monitoring results to a file

def write_json_compressed(records, file_path):
    json_str = json.dumps([r.to_kvpairs(raw=True) for r in records], indent=4)
    compressed = zlib.compress(json_str.encode())
    with open(file_path, 'wb') as f:
        f.write(compressed)

def write_json(records, file_path):
    json_str = json.dumps([r.to_kvpairs(raw=True) for r in records], indent=4)
    with open(file_path, 'w') as f:
        f.write(json_str)

def add_fake_snapshot_if_needed(records):
    '''
    perf and record file format stores only snapshot end time.  For a record
    having only single snapshot, hence, the reader of the files cannot know the
    start time of the snapshot.  Add a fake snapshot for the case.
    '''

    for record in records:
        snapshots = record.snapshots
        if len(snapshots) != 1:
            continue
        snapshot = snapshots[0]
        snap_duration = snapshot.end_time - snapshot.start_time
        # -1 nr_accesses.samples / -1 age.aggr_intervals means fake
        fake_regions = [_damon.DamonRegion(0, 0,
            -1, _damon.unit_samples, -1, _damon.unit_aggr_intervals)]
        fake_snapshot = DamonSnapshot(snapshot.end_time,
                snapshot.end_time + snap_duration, fake_regions, None)
        snapshots.append(fake_snapshot)

def write_perf_script(records, file_path):
    '''
    Example of the normal perf script output:

    kdamond.0  4452 [000] 82877.315633: damon:damon_aggregated: \
            target_id=18446623435582458880 nr_regions=17 \
            140731667070976-140731668037632: 0 3
    '''

    add_fake_snapshot_if_needed(records)
    with open(file_path, 'w') as f:
        for record in records:
            snapshots = record.snapshots
            for snapshot in snapshots:
                for region in snapshot.regions:
                    f.write(' '.join(['kdamond.x', 'xxxx', 'xxxx',
                        '%f:' % (snapshot.end_time / 1000000000.0),
                        'damon:damon_aggregated:',
                        'target_id=%s' % record.target_id,
                        'nr_regions=%d' % len(snapshot.regions),
                        '%d-%d: %d %s' % (region.start, region.end,
                            region.nr_accesses.samples,
                            region.age.aggr_intervals)]) + '\n')

def parse_file_permission_str(file_permission_str):
    try:
        file_permission = int(file_permission_str, 8)
    except Exception as e:
        return None, 'parsing failed (%s)' % e
    if file_permission < 0o0 or file_permission > 0o777:
        return None, 'out of available permission range'
    return file_permission, None

file_type_perf_script = 'perf_script'   # perf script output
file_type_perf_data = 'perf_data'       # perf record result file
file_type_json = 'json'                 # list of DamonRecord objects in json
file_type_json_compressed = 'json_compressed'

file_types = [file_type_json_compressed, file_type_json, file_type_perf_script,
        file_type_perf_data]
self_write_supported_file_types = [file_type_json_compressed, file_type_json,
        file_type_perf_script]

def write_damon_records(records, file_path, file_type, file_permission=None):
    '''Returns None if success, an error string otherwise'''
    if not file_type in self_write_supported_file_types:
        return 'write unsupported file type: %s' % file_type

    if file_type == file_type_json_compressed:
        write_json_compressed(records, file_path)
    elif file_type == file_type_json:
        write_json(records, file_path)
    elif file_type == file_type_perf_script:
        write_perf_script(records, file_path)

    if file_permission is not None:
        os.chmod(file_path, file_permission)
    return None

def rewrite_record_file(src_file, dst_file, file_format, file_permission=None,
        monitoring_intervals=None):
    records, err = parse_records_file(src_file, monitoring_intervals)
    if err:
        return err
    return write_damon_records(records, dst_file, file_format,
            file_permission)

def update_records_file(file_path, file_format, file_permission=None,
        monitoring_intervals=None):
    return rewrite_record_file(file_path, file_path, file_format,
            file_permission, monitoring_intervals)

# for recording

# Meaning of the fields of ProcMemFootprint are as below.
#
# ======== ===============================       ==============================
# Field    Content
# ======== ===============================       ==============================
# size     total program size (pages)            (same as VmSize in status)
# resident size of memory portions (pages)       (same as VmRSS in status)
# shared   number of pages that are shared       (i.e. backed by a file, same
#                                                as RssFile+RssShmem in status)
# trs      number of pages that are 'code'       (not including libs; broken,
#                                                includes data segment)
# lrs      number of pages of library            (always 0 on 2.6)
# drs      number of pages of data/stack         (including libs; broken,
#                                                includes library text)
# dt       number of dirty pages                 (always 0 on 2.6)
# ======== ===============================       ==============================
#
# The above table is stolen from Documentation/filesystems/proc.rst file of
# Linux
class ProcMemFootprint:
    size = None
    resident = None
    shared = None
    trs = None
    lrs = None
    drs = None
    dt = None

    def __init__(self, pid=None):
        if pid is None:
            return

        try:
            with open('/proc/%s/statm' % pid, 'r') as f:
                fields = [int(x) for x in f.read().split()]
        except:
            # the process may terminated.  Just think it as not using memory.
            fields = [0 for _ in range(7)]
        self.size = fields[0]
        self.resident = fields[1]
        self.shared = fields[2]
        self.trs = fields[3]
        self.lrs = fields[4]
        self.drs = fields[5]
        self.dt = fields[6]

    def to_kvpairs(self):
        return self.__dict__

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls()
        self.size = kvpairs['size']
        self.resident = kvpairs['resident']
        self.shared = kvpairs['shared']
        self.trs = kvpairs['trs']
        self.lrs = kvpairs['lrs']
        self.drs = kvpairs['drs']
        self.dt = kvpairs['dt']
        return self

class SysMemFootprint:
    total = None
    free = None
    available = None
    buffers = None
    cached = None

    def __init__(self, populate):
        if populate is False:
            return
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                fields = line.split()
                if fields[0] == 'MemTotal:':
                    self.total = int(fields[1])
                if fields[0] == 'MemFree:':
                    self.free = int(fields[1])
                if fields[0] == 'MemAvailable:':
                    self.available = int(fields[1])
                if fields[0] == 'Buffers:':
                    self.buffers = int(fields[1])
                if fields[0] == 'Cached:':
                    self.cached = int(fields[1])

    def to_kvpairs(self):
        return self.__dict__

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(populate=False)
        self.total = kvpairs['total']
        self.free = kvpairs['free']
        self.available = kvpairs['available']
        self.buffers = kvpairs['buffers']
        self.cached = kvpairs['cached']
        return self

class MemFootprintsSnapshot:
    time = None
    footprints = None

    def __init__(self, pids=None):
        if pids is None:
            return

        self.time = time.time()
        self.footprints = {}
        for pid in pids:
            self.footprints[pid] = ProcMemFootprint(pid)
        self.footprints['sys'] = SysMemFootprint(populate=True)

    def to_kvpairs(self):
        footprints = []
        for target, fp in self.footprints.items():
            if target == 'sys':
                pid = None
            else:
                pid = target
            footprints.append({'pid': pid, 'footprint': fp.to_kvpairs()})
        return {'time': self.time, 'footprints': footprints}

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls()
        self.time = kvpairs['time']
        self.footprints = {}
        for fp in kvpairs['footprints']:
            pid, footprint = fp['pid'], fp['footprint']
            if pid is None:
                self.footprints[pid] = SysMemFootprint.from_kvpairs(footprint)
            else:
                self.footprints[pid] = ProcMemFootprint.from_kvpairs(footprint)
        return self

def record_mem_footprint(kdamonds, snapshots):
    pids = []
    for kdamond in kdamonds:
        for ctx in kdamond.contexts:
            for target in ctx.targets:
                if target.pid is None:
                    continue
                pids.append(target.pid)
    snapshots.append(MemFootprintsSnapshot(pids))

def save_mem_footprint(snapshots, filepath, file_permission):
    with open(filepath, 'w') as f:
        json.dump([s.to_kvpairs() for s in snapshots], f, indent=4)
    os.chmod(filepath, file_permission)

def load_mem_footprint(filepath):
    with open(filepath, 'r') as f:
        kvpairs = json.load(f)
    return [MemFootprintsSnapshot.from_kvpairs(x) for x in kvpairs]

class Vma:
    start = None
    end = None
    name = None

    def __init__(self, start, end, name):
        self.start = start
        self.end = end
        self.name = name

    def to_kvpairs(self):
        return self.__dict__

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(None, None, None)
        self.start = kvpairs['start']
        self.end = kvpairs['end']
        self.name = kvpairs['name']

class ProcVmas:
    pid = None
    vmas = None

    def __init__(self, pid):
        self.pid = pid
        self.vmas = []

        if pid is None:
            return

        try:
            with open('/proc/%s/maps' % pid, 'r') as f:
                for line in f:
                    fields = line.split()
                    start, end = [int(addr, 16) for addr in fields[0].split('-')]
                    name = fields[-1]
                    self.vmas.append(Vma(start, end, name))
        except:
            # the process may terminated.
            return

    def to_kvpairs(self):
        kvpairs = {'pid': self.pid}
        kvpairs['vmas'] = [v.to_kvpairs() for v in self.vmas]
        return kvpairs

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(None)
        self.pid = kvpairs['pid']
        self.vmas = [Vma.from_kvpairs(kvp) for kvp in kvpairs['vmas']]

class ProcVmasSnapshot:
    time = None
    procvmas = None

    def __init__(self, pids):
        if pids is None:
            return

        self.time = time.time()
        self.procvmas = []
        for pid in pids:
            self.procvmas.append(ProcVmas(pid))

    def to_kvpairs(self):
        kvpairs = {'time': self.time}
        kvpairs['procvmas'] = [p.to_kvpairs() for p in self.procvmas]
        return kvpairs

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(None)
        self.time = kvpairs['time']
        self.procvmas = [ProcVmas.from_kvpairs(kvp)
                         for kvp in kvapirs['procvmas']]

def record_proc_vmas(kdamonds, snapshots):
    pids = []
    for kdamond in kdamonds:
        for ctx in kdamond.contexts:
            for target in ctx.targets:
                if target.pid is None:
                    continue
                pids.append(target.pid)
    snapshots.append(ProcVmasSnapshot(pids))

def save_proc_vmas(snapshots, filepath, file_permission):
    with open(filepath, 'w') as f:
        json.dump([s.to_kvpairs() for s in snapshots], f, indent=4)
    os.chmod(filepath, file_permission)

def load_proc_vmas(filepath):
    with open(filepath, 'r') as f:
        kvpairs = json.load(f)
    return [ProcVmasSnapshot.from_kvpairs(x) for x in kvpairs]

class ProcStat:
    fields = None

    def __init__(self, pid):
        if pid is None:
            return
        try:
            with open('/proc/%s/stat' % pid, 'r') as f:
                self.fields = f.read().split()
        except Exception:
            # the process may finished already
            pass

    def to_kvpairs(self):
        return {
                'fields': self.fields,
                }

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(None)
        self.fields = kvpairs['fields']

    def __str__(self):
        if self.fields is None:
            return 'uninitialized'
        # from Documentation/filesystesm/proc.rst of Linux source tree
        field_names = ['pid', 'tcomm', 'state', 'ppid', 'pgrp', 'sid',
                       'tty_nr', 'tty_pgrp', 'flags', 'min_flt', 'cmin_flt',
                       'maj_flt', 'cmaj_flt', 'utime', 'stime', 'cutime',
                       'cstime', 'priority', 'nice', 'num_threads',
                       'it_real_value', 'start_time', 'vsize', 'rss', 'rsslim',
                       'start_code', 'end_code', 'start_stack', 'esp', 'eip',
                       'pending', 'blocked', 'sigign', 'sigcatch', '0', '0',
                       '0', 'exit_signal', 'task_cpu', 'rt_priority', 'policy',
                       'blkio_ticks', 'gtime', 'cgtime', 'start_data',
                       'end_data', 'start_brk', 'arg_start', 'arg_end',
                       'env_start', 'env_end', 'exit_code']
        lines = []
        for idx, field_name in enumerate(field_names):
            lines.append('%s: %s' % (field_name, self.fields[idx]))
        return '\n'.join(lines)

class ProcStatsSnapshot:
    time = None
    proc_stats = None

    def __init__(self, pids):
        if pids is None:
            return

        self.time = time.time()
        self.proc_stats = []
        for pid in pids:
            self.proc_stats.append(ProcStat(pid))

    def to_kvpairs(self):
        kvpairs = {'time': self.time}
        kvpairs['proc_stats'] = [p.to_kvpairs() for p in self.proc_stats]
        return kvpairs

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls(None)
        self.time = kvpairs['time']
        self.proc_stats = [ProcStat.from_kvpairs(kvp)
                         for kvp in kvapirs['proc_stats']]

def record_proc_stats(kdamonds, snapshots):
    pids = []
    for kdamond in kdamonds:
        pids.append(kdamond.pid)
        for ctx in kdamond.contexts:
            for target in ctx.targets:
                if target.pid is None:
                    continue
                pids.append(target.pid)
    snapshots.append(ProcStatsSnapshot(pids))

def save_proc_stats(snapshots, filepath, file_permission):
    with open(filepath, 'w') as f:
        json.dump([s.to_kvpairs() for s in snapshots], f, indent=4)
    os.chmod(filepath, file_permission)

def load_proc_stats(filepath):
    with open(filepath, 'r') as f:
        kvpairs = json.load(f)
    return [ProcStatsSnapshot.from_kvpairs(x) for x in kvpairs]

def add_childs_target(kdamonds):
    # TODO: Support multiple kdamonds
    if not _damon.target_has_pid(kdamonds[0].contexts[0].ops):
        return
    current_targets = kdamonds[0].contexts[0].targets

    for target in current_targets:
        if target.pid is None:
            continue
        try:
            childs_pids = subprocess.check_output(
                    ['ps', '--ppid', '%s' % target.pid, '-o', 'pid=']
                    ).decode().split()
        except:
            childs_pids = []
        if len(childs_pids) == 0:
            continue

        # TODO: Commit all at once, out of this loop
        new_targets = []
        for child_pid in childs_pids:
            # skip the child if already in the targets
            if child_pid in ['%s' % t.pid for t in current_targets]:
                continue
            # remove already terminated targets, since committing already
            # terminated targets to DAMON fails
            new_targets = [target for target in current_targets
                    if pid_running('%s' % target.pid)]
            new_targets.append(_damon.DamonTarget(pid=child_pid, regions=[]))
        if new_targets == []:
            continue

        # commit the new set of targets
        kdamonds[0].contexts[0].targets = new_targets
        err = _damon.commit(kdamonds)
        if err is not None:
            return 'commit failed (%s)' % err
    return None

def pid_running(pid):
    '''pid should be string'''
    try:
        subprocess.check_output(['ps', '--pid', pid])
        return True
    except:
        return False

def all_targets_terminated(targets):
    for target in targets:
        if pid_running('%s' % target.pid):
            return False
    return True

def poll_target_pids(kdamonds):
    '''Return True if >=1 target processes are running'''
    has_running_process = False
    if not kdamonds:
        return False
    for kdamond in kdamonds:
        for ctx in kdamond.contexts:
            if not _damon.target_has_pid(ctx.ops):
                continue
            if not all_targets_terminated(ctx.targets):
                return True
    return False

class RecordingHandle:
    '''
    Specifies the recording request.  The recording can be started by
    start_recording(), and finished by finish_recording().

    As a result of the two function calls, below files can be generated.

    - f'{handle.file_path}.kdamonds'
      - Given Kdamonds for the recording.  Have a json list of Kdamond kvpair
        objects.
    f'{handle.file_path}'
      - The DAMON monitoring results.  Have a json list of DamonRecord kvpair
        objects.  Each DamonRecord is for each target or scheme of the kdamond.
    f'{handle.file_path}.profile'
      - 'perf record' output file.
    f'{handle.file_path}.mem_footprint'
      - System and monitoring target process memory footprints.  Have a json
        list of MemFootprintsSnapshot kvpair objects.
    f'{handle.file_path}.vmas'
      - Monitoring target process memory mappings.  Have a json list of
        ProcVmaSnapshot kvpair objects.
    f'{handle.file_path}.proc_stats'
      - Kdamonds and monitoring target processes /proc/PID/stat contents.  Have
        a json list of ProcStatsSnapshot kvpair objects.
    '''

    file_path = None
    file_format = None
    file_permission = None

    # for access patterns tracing
    tracepoint = None
    monitoring_intervals = None
    perf_pipe = None

    # for access patterns snapshot
    snapshot_request = None
    snapshot_records = None
    snapshot_count = None
    snapshot_interval_sec = None

    # for CPU clock event recording
    do_profile = None
    perf_profile_pipe = None

    # for adding child tasks and memory footprint recording
    kdamonds = None
    add_child_tasks = None
    mem_footprint_snapshots = None

    # for vmas recording
    vmas_snapshots = None

    # for /proc/<pid>/stat recording
    proc_stats = None

    timeout = None

    def __init__(self, tracepoint, file_path, file_format, file_permission,
                 monitoring_intervals,
                 do_profile,
                 kdamonds, add_child_tasks, record_mem_footprint,
                 record_vmas, timeout):
        self.tracepoint = tracepoint
        self.file_path = file_path
        self.file_format = file_format
        self.file_permission = file_permission
        self.monitoring_intervals = monitoring_intervals

        self.do_profile = do_profile

        self.kdamonds = kdamonds
        self.add_child_tasks = add_child_tasks
        if record_mem_footprint is True:
            self.mem_footprint_snapshots = []
        if record_vmas is True:
            self.vmas_snapshots = []

        self.proc_stats = []

        self.timeout = timeout

def start_recording(handle):
    kdamonds_file_path = '%s.kdamonds' % handle.file_path
    with open(kdamonds_file_path, 'w') as f:
        json.dump([k.to_kvpairs() for k in handle.kdamonds], f, indent=4)
    os.chmod(kdamonds_file_path, handle.file_permission)

    if handle.tracepoint is not None:
        handle.perf_pipe = subprocess.Popen(
                [PERF, 'record', '-a', '-e', handle.tracepoint,
                 '-o', handle.file_path])
    if handle.do_profile:
        cmd = [PERF, 'record', '-o', '%s.profile' % handle.file_path]
        handle.perf_profile_pipe = subprocess.Popen(cmd)

    start_time = time.time()
    nr_snapshots_to_take = handle.snapshot_count
    if handle.snapshot_interval_sec:
        sleep_time = handle.snapshot_interval_sec
    else:
        sleep_time = 1
    while (poll_target_pids(handle.kdamonds) or
           _damon.any_kdamond_running()):
        if handle.add_child_tasks is True:
            add_childs_target(handle.kdamonds)

        if handle.mem_footprint_snapshots is not None:
            record_mem_footprint(handle.kdamonds,
                                 handle.mem_footprint_snapshots)
        if handle.vmas_snapshots is not None:
            record_proc_vmas(handle.kdamonds, handle.vmas_snapshots)

        record_proc_stats(handle.kdamonds, handle.proc_stats)
        if (handle.timeout is not None and
            time.time() - start_time >= handle.timeout):
            break

        if handle.snapshot_request:
            if handle.snapshot_records is None:
                handle.snapshot_records = []
            snapshot_records, err = get_snapshot_records_of(
                    handle.snapshot_request)
            if err is not None:
                print('failed getting snapshot')
                exit(1)
            handle.snapshot_records += snapshot_records
            nr_snapshots_to_take -= 1
            if nr_snapshots_to_take == 0:
                handle.snapshot_records = merge_records(
                        handle.snapshot_records)
                break

        time.sleep(sleep_time)

def finish_recording(handle):
    if handle.perf_pipe:
        try:
            handle.perf_pipe.send_signal(signal.SIGINT)
            handle.perf_pipe.wait()
        except:
            # perf might already finished
            pass

        if handle.file_format == file_type_perf_data:
            os.chmod(handle.file_path, handle.file_permission)
        else:
            err = update_records_file(handle.file_path, handle.file_format,
                    handle.file_permission, handle.monitoring_intervals)
            if err is not None:
                print('converting format from perf_data to %s failed (%s)' %
                        (handle.file_format, err))

    if handle.snapshot_records:
        write_damon_records(handle.snapshot_records, handle.file_path,
                            handle.file_format, handle.file_permission)

    if handle.perf_profile_pipe is not None:
        try:
            handle.perf_profile_pipe.send_signal(signal.SIGINT)
        except:
            # perf might already finished
            pass
        os.chmod('%s.profile' % handle.file_path, handle.file_permission)

    if handle.mem_footprint_snapshots is not None:
        save_mem_footprint(
                handle.mem_footprint_snapshots,
                '%s.mem_footprint' % handle.file_path, handle.file_permission)
    if handle.vmas_snapshots is not None:
        save_proc_vmas(handle.vmas_snapshots, '%s.vmas' % handle.file_path,
                       handle.file_permission)
    save_proc_stats(handle.proc_stats, '%s.proc_stats' % handle.file_path,
                    handle.file_permission)

# for snapshot

def find_install_scheme(scheme_to_find):
    '''Install given scheme to all contexts if effectively same scheme is not
    installed.
    Returns whether it found a context doesn't having the scheme, indices list
    for the effectively same schemes, and an error if something wrong.
    '''
    installed = False
    indices = []
    kdamonds = _damon.current_kdamonds()
    for kidx, kdamond in enumerate(kdamonds):
        for cidx, ctx in enumerate(kdamond.contexts):
            ctx_has_the_scheme = False
            for sidx, scheme in enumerate(ctx.schemes):
                if scheme.effectively_equal(scheme_to_find, ctx.intervals):
                    if _damon.feature_supported('schemes_apply_interval'):
                        scheme_to_find.apply_interval_us = ctx.intervals.sample
                    ctx_has_the_scheme = True
                    indices.append([kidx, cidx, sidx])
                    break
            if ctx_has_the_scheme:
                continue

            if _damon.feature_supported('schemes_apply_interval'):
                scheme_to_find.apply_interval_us = ctx.intervals.sample
            ctx.schemes.append(scheme_to_find)
            installed = True
            indices.append([kidx, cidx, len(ctx.schemes) - 1])
    if installed:
        err = _damon.commit(kdamonds)
        if err is not None:
            return (False, [],
                    'committing scheme installed kdamonds failed: %s' % err)
    return installed, indices, None

def tried_regions_to_snapshot(scheme, intervals, merge_regions):
    snapshot_end_time_ns = time.time() * 1000000000
    snapshot_start_time_ns = snapshot_end_time_ns - intervals.aggr * 1000
    regions = []

    for tried_region in scheme.tried_regions:
        '''Merge regions that having same access pattern, since DAMON usually
        splits regions unnecessarily to keep the min_nr_regions'''
        if merge_regions and len(regions) > 0:
            last_region = regions[-1]
            if (last_region.end == tried_region.start and
                    last_region.nr_accesses == tried_region.nr_accesses and
                    last_region.age == tried_region.age):
                last_region.end = tried_region.end
                continue
        regions.append(tried_region)
    if scheme.tried_bytes is not None:
        total_bytes = scheme.tried_bytes
    else:
        total_bytes = None

    return DamonSnapshot(snapshot_start_time_ns, snapshot_end_time_ns, regions,
            total_bytes)

def tried_regions_to_records_of(idxs, merge_regions):
    '''idxs: list of kdamond/context/scheme indices to get records for.  If it
    is None, return records for all schemes'''
    records = []
    for kdamond_idx, kdamond in enumerate(_damon.current_kdamonds()):
        if kdamond.state != 'on':
            continue
        for ctx_idx, ctx in enumerate(kdamond.contexts):
            for scheme_idx, scheme in enumerate(ctx.schemes):
                if not [kdamond_idx, ctx_idx, scheme_idx] in idxs:
                    continue

                snapshot = tried_regions_to_snapshot(scheme, ctx.intervals,
                        merge_regions)

                records.append(DamonRecord(kdamond_idx, ctx_idx, ctx.intervals,
                    scheme_idx, None))
                records[-1].snapshots.append(snapshot)
                break
    return records

def three_regions_of(pid):
    '''
    Return three big mapped virtual address ranges of a given process, which
    separated by the two huge gaps[1].

    [1] https://docs.kernel.org/mm/damon/design.html#vma-based-target-address-range-construction
    '''
    if not os.path.isfile('/proc/%s/maps' % pid):
        print('maps file for %s pid not found' % pid)
        exit(0)
    with open('/proc/%s/maps' % pid, 'r') as f:
        maps_content = f.read()
    regions = []
    for line in maps_content.split('\n'):
        if line == '':
            continue
        start, end = [int(addr, 16) for addr in line.split()[0].split('-')]
        if len(regions) > 0 and regions[-1].end == start:
            regions[-1].end = end
        else:
            regions.append(_damon.DamonRegion(start, end))

    gaps = []
    for idx, region in enumerate(regions):
        if idx == 0:
            continue
        prev_region = regions[idx - 1]
        if region.start != prev_region.end:
            gaps.append([prev_region.end, region.start])
    gaps.sort(key=lambda x: x[1] - x[0], reverse=True)
    if len(gaps) < 2:
        return regions
    # sort biggest two gaps in address
    gaps = sorted(gaps[:2], key=lambda x: x[0])

    return [_damon.DamonRegion(regions[0].start, gaps[0][0]),
            _damon.DamonRegion(gaps[0][1], gaps[1][0]),
            _damon.DamonRegion(gaps[1][1], regions[-1].end)]

def install_target_regions_if_needed(kdamonds):
    '''Returns an error string, or None'''
    need_install = False
    for kd in kdamonds:
        for ctx in kd.contexts:
            if ctx.ops != 'vaddr':
                continue
            need_install = True
            for target in ctx.targets:
                target.regions = three_regions_of(target.pid)
    if not need_install:
        return None
    err = _damon.commit(kdamonds)
    for kd in kdamonds:
        for ctx in kd.contexts:
            if ctx.ops != 'vaddr':
                continue
            for target in ctx.targets:
                target.regions = []
    return err

def update_get_snapshot_records(kdamond_idxs, scheme_idxs,
        total_sz_only, merge_regions):
    if total_sz_only:
        err = _damon.update_schemes_tried_bytes(kdamond_idxs)
        # update_schemes_tried_bytes() can error if the feature is not
        # supported.  Then, full record will be returned
        if err is None:
            records = tried_regions_to_records_of(scheme_idxs, merge_regions)
            return records, None

    err = 'assumed error'
    nr_tries = 0
    while err is not None and nr_tries < 5:
        nr_tries += 1

        err = _damon.update_schemes_tried_regions(kdamond_idxs)

        if err is not None:
            time.sleep(random.randrange(
                2**(nr_tries - 1), 2**nr_tries) / 100)
    if err is not None:
        return None, 'updating schemes tried regions fail: %s' % err

    records = tried_regions_to_records_of(scheme_idxs, merge_regions)
    return records, None

def get_snapshot_records(monitor_scheme, total_sz_only, merge_regions):
    'return DamonRecord objects each having single DamonSnapshot and an error'
    running_kdamond_idxs = _damon.running_kdamond_idxs()
    if len(running_kdamond_idxs) == 0:
        return None, 'no kdamond running'

    orig_kdamonds = _damon.current_kdamonds()

    err = install_target_regions_if_needed(orig_kdamonds)
    if err is not None:
        return None, 'vaddr region install failed (%s)' % err

    installed, idxs, err = find_install_scheme(monitor_scheme)
    if err:
        return None, 'monitoring scheme install failed: %s' % err

    records, err = update_get_snapshot_records(running_kdamond_idxs, idxs,
            total_sz_only, merge_regions)

    if installed:
        uninstall_err = _damon.commit(orig_kdamonds)
        if uninstall_err:
            errmsg = 'monitoring scheme uninstall failed: %s' % uninstall_err
            if err is not None:
                err += ', %s' % errmsg
            else:
                err = errmsg

    return records, err

def get_snapshot_records_for_schemes(idxs, total_sz_only, merge_regions):
    '''idxs: list of kdamond/context/scheme indices to get records for.
    Return DamonRecord objects each having single DamonSnapshot and an error'''
    running_kdamond_idxs = _damon.running_kdamond_idxs()
    if len(running_kdamond_idxs) == 0:
        return None, 'no kdamond running'

    return update_get_snapshot_records(running_kdamond_idxs, idxs,
            total_sz_only, merge_regions, None)

def region_of_pattern(region, pattern, record_intervals):
    sz_bytes = pattern.sz_bytes
    nr_acc = pattern.nr_acc_min_max
    age = pattern.age_min_max
    # return if the region fits into the pattern
    sz = region.size()
    if sz < sz_bytes[0] or sz_bytes[1] < sz:
        return False

    if record_intervals is None:
        return True
    region.nr_accesses.add_unset_unit(record_intervals)
    freq = region.nr_accesses.percent
    if freq < nr_acc[0].percent or nr_acc[1].percent < freq:
        return False
    region.age.add_unset_unit(record_intervals)
    usecs = region.age.usec
    if usecs < age[0].usec or age[1].usec < usecs:
        return False
    return True

def filter_by_pattern(record, access_pattern):
    for snapshot in record.snapshots:
        filtered = []
        for region in snapshot.regions:
            if region_of_pattern(region, access_pattern, record.intervals):
                filtered.append(region)
        snapshot.regions = filtered

def filter_by_addr(region, addr_ranges):
    regions = []
    for start, end in addr_ranges:
        # out of the range
        if region.end <= start or end <= region.start:
            continue
        # in the range
        if start <= region.start and region.end <= end:
            regions.append(copy.deepcopy(region))
            continue
        # overlap
        copied = copy.deepcopy(region)
        copied.start = max(start, region.start)
        copied.end = min(end, region.end)
        regions.append(copied)
    return regions

def filter_records_by_addr(records, addr_ranges):
    for record in records:
        for snapshot in record.snapshots:
            filtered_regions = []
            for region in snapshot.regions:
                filtered_regions += filter_by_addr(region, addr_ranges)
            snapshot.regions = filtered_regions
            snapshot.update_total_bytes()

def filter_records_by_snapshot_sz(records, sz_ranges):
    for record in records:
        filtered_snapshots = []
        for snapshot in record.snapshots:
            for min_, max_ in sz_ranges:
                if (min_ <= snapshot.total_bytes and
                        snapshot.total_bytes <= max_):
                    filtered_snapshots.append(snapshot)
                    break
        record.snapshots = filtered_snapshots

def filter_records_by_snapshot_time(records, time_ranges):
    for record in records:
        filtered_snapshots = []
        for snapshot in record.snapshots:
            filter_out = True
            for start_sec, end_sec in time_ranges:
                if (snapshot.start_time >= start_sec and
                    snapshot.end_time <= end_sec):
                    filter_out = False
                    break
            if filter_out is False:
                filtered_snapshots.append(snapshot)
        record.snapshots = filtered_snapshots

def filter_records_by_temperature(records, temperature_ranges,
                                  temperature_weights):
    for record in records:
        for snapshot in record.snapshots:
            filtered_regions = []
            for region in snapshot.regions:
                temperature = damo_report_access.temperature_of(
                        region, temperature_weights)
                for min_t, max_t in temperature_ranges:
                    if min_t <= temperature and temperature <= max_t:
                        filtered_regions.append(region)
                        break
            snapshot.regions = filtered_regions
            snapshot.update_total_bytes()

def get_snapshot_records_of(request):
    '''
    get records containing single snapshot from running kdamonds
    '''
    if request.tried_regions_of is None:
        filters = []
        if request.record_filter:
            addr_ranges = request.record_filter.address_ranges
            if addr_ranges and _damon.feature_supported('schemes_filters_addr'):
                for start, end in addr_ranges:
                    filters.append(_damon.DamosFilter(
                        'addr', False,
                        address_range=_damon.DamonRegion(start, end)))
            monitor_scheme = _damon.Damos(
                    access_pattern=request.record_filter.access_pattern,
                    filters=filters)

        else:
            monitor_scheme = _damon.Damos()

        records, err = get_snapshot_records(monitor_scheme,
                request.total_sz_only, not request.dont_merge_regions)
    else:
         records, err = get_snapshot_records_for_schemes(
                 request.tried_regions_of, request.total_sz_only,
                 not request.dont_merge_regions)
    return records, err

class RecordFilter:
    access_pattern = None
    address_ranges = None
    snapshot_sz_ranges = None
    snapshot_time_ranges = None
    temperature_ranges = None
    temperature_weights = None

    def __init__(self, access_pattern, address_ranges, snapshot_sz_ranges,
                 snapshot_time_ranges, temperature_ranges, temperature_weights):
        self.access_pattern = access_pattern
        self.address_ranges = address_ranges
        self.snapshot_sz_ranges = snapshot_sz_ranges
        self.snapshot_time_ranges = snapshot_time_ranges
        self.temperature_ranges = temperature_ranges
        self.temperature_weights = temperature_weights

    def to_kvpairs(self, raw):
        kvpairs = {'access_pattern': self.access_pattern.to_kvpairs(raw)}
        if self.address_ranges is None:
            address_ranges = None
        else:
            address_ranges = [
                    [_damo_fmt_str.format_sz(start, raw),
                     _damo_fmt_str.format_sz(end, raw)]
                    for start, end in self.address_ranges]
        kvpairs['address_ranges'] = address_ranges
        if self.snapshot_sz_ranges is None:
            snapshot_sz_ranges = None
        else:
            snapshot_sz_ranges = [
                    [_damo_fmt_str.format_sz(start, raw),
                     _damo_fmt_str.format_sz(end, raw)]
                    for start, end in self.snapshot_sz_ranges]
        kvpairs['snapshot_sz_ranges'] = snapshot_sz_ranges
        kvpairs['temperature_ranges'] = self.temperature_ranges
        kvpairs['temperature_weights'] = self.temperature_weights
        return kvpairs

    def filter_records(self, records):
        if self.access_pattern is not None:
            for record in records:
                filter_by_pattern(record, self.access_pattern)
        if self.address_ranges is not None:
            filter_records_by_addr(records, self.address_ranges)
        if self.snapshot_sz_ranges is not None:
            filter_records_by_snapshot_sz(records, self.snapshot_sz_ranges)
        if self.snapshot_time_ranges is not None:
            filter_records_by_snapshot_time(records, self.snapshot_time_ranges)
        if self.temperature_ranges is not None:
            filter_records_by_temperature(records, self.temperature_ranges,
                                          self.temperature_weights)

class RecordGetRequest:
    # TODO: Extend to be used for recording

    # source of the record.  If both are None, get snapshot
    tried_regions_of = None
    record_file = None

    record_filter = None

    # more detailed requests
    total_sz_only = None
    dont_merge_regions = None

    def __init__(
            self, tried_regions_of=None, record_file=None, record_filter=None,
            total_sz_only=False, dont_merge_regions=True):
        self.tried_regions_of = tried_regions_of
        self.record_file = record_file
        self.record_filter = record_filter
        self.total_sz_only = total_sz_only
        self.dont_merge_regions = dont_merge_regions

def get_records(tried_regions_of=None, record_file=None, record_filter=None,
                total_sz_only=False, dont_merge_regions=True):
    request = RecordGetRequest(
            tried_regions_of, record_file, record_filter,
            total_sz_only, dont_merge_regions)

    # If record is live snapshot, access pattern filtering is applied with
    # get_snapshot_records_of() because it uses DAMOS to get the snapshot.  If
    # the kernel has schemes_filters_addr feature, address ranges filter is
    # also applied.  Also, snapshot time range filter makes no sense for live
    # snapshot.
    # To avoid confusing caller, copy filter, modify the filter as necessary
    # and apply only necessary filters at once at last stage.
    if record_filter:
        filter_copy = copy.deepcopy(record_filter)
    else:
        filter_copy = RecordFilter(None, None, None, None, None, None)

    if request.record_file is None:
        records, err = get_snapshot_records_of(request)
        if err is not None:
            return None, err
        filter_copy.access_pattern = None
        if _damon.feature_supported('schemes_filters_addr'):
            filter_copy.address_ranges = None
            filter_copy.snapshot_time_ranges = None
    else:
        if not os.path.isfile(request.record_file):
            return None, '%s not found' % request.record_file

        records, err = parse_records_file(request.record_file)
        if err:
            return None, ('parsing %s failed (%s)' %
                    (request.record_file, err))

    filter_copy.filter_records(records)
    return records, None

def parse_sort_bytes_ranges_input(bytes_ranges_input):
    try:
        ranges = [[_damo_fmt_str.text_to_bytes(start),
            _damo_fmt_str.text_to_bytes(end)]
            for start, end in bytes_ranges_input]
    except Exception as e:
        return None, 'conversion to bytes failed (%s)' % e

    ranges.sort(key=lambda x: x[0])
    for idx, arange in enumerate(ranges):
        start, end = arange
        if start > end:
            return None, 'start > end (%s)' % arange
        if idx > 0 and ranges[idx - 1][1] > start:
            return None, 'overlapping range'
    return ranges, None

def args_to_filter(args):
    access_pattern = _damon.DamosAccessPattern(args.sz_region,
            args.access_rate, _damon.unit_percent, args.age * 1000000,
            _damon.unit_usec)

    addr_range = None
    if args.address is not None:
        addr_range, err = parse_sort_bytes_ranges_input(
                args.address)
        if err is not None:
            return None, 'wrong --address input (%s)' % err

    snapshot_sz_ranges = None
    if args.sz_snapshot is not None:
        snapshot_sz_ranges, err = parse_sort_bytes_ranges_input(
                args.sz_snapshot)
        if err is not None:
            return None, 'wrong --sz_snapshot input (%s)' % err

    snapshot_time = None
    if args.snapshot_time is not None:
        snapshot_time = [
                [_damo_fmt_str.text_to_ns(s), _damo_fmt_str.text_to_ns(e)]
                for s, e in args.snapshot_time]

    if hasattr(args, 'temperature_weights'):
        temperature_weights = args.temperature_weights
    else:
        # ignore size
        temperature_weights = [0, 100, 100]

    return RecordFilter(access_pattern, addr_range,
                        snapshot_sz_ranges, snapshot_time,
                        args.temperature, temperature_weights), None

def set_filter_argparser(parser):
    parser.add_argument('--sz_region', metavar=('<min>', '<max>'), nargs=2,
            default=['min', 'max'],
            help='min/max size of regions (bytes) to show')
    parser.add_argument('--access_rate', metavar=('<min>', '<max>'), nargs=2,
            default=['min', 'max'],
            help='min/max access rate of regions (percent) to show')
    parser.add_argument('--age', metavar=('<min>', '<max>'), nargs=2,
            default=['min', 'max'],
            help='min/max age of regions (seconds) to show')
    parser.add_argument('--address', metavar=('<start>', '<end>'), nargs=2,
            action='append',
            help='address ranges to show')
    parser.add_argument(
            '--sz_snapshot', metavar=('<min>', '<max>'), nargs=2,
            action='append',
            help='min/max total size of regions of snapshots to show')
    parser.add_argument(
            '--snapshot_time', metavar=('<start (ns)>', '<end (ns)>'), nargs=2,
            action='append',
            help='show snapshots generated in these time intervals')
    parser.add_argument(
            '--temperature', metavar=('<min>', '<max>'), nargs=2, type=int,
            action='append',
            help='min/max temperature of regions to show')
