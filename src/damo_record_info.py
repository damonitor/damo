# SPDX-License-Identifier: GPL-2.0

"""
Print basic information of the access monitoring results record file.
"""

import _damo_fmt_str
import _damo_records

class GuideRegion:
    start_addr = None
    end_addr = None
    heats = None

    def heat_per_byte(self):
        if self.heats is None:
            return 0
        return float(self.heats) / (self.end_addr - self.start_addr)

    def __init__(self, start_addr, end_addr):
        self.start_addr = start_addr
        self.end_addr = end_addr

class GuideInfo:
    kdamond_idx = None
    context_idx = None
    scheme_idx = None
    tid = None
    start_time = None
    end_time = None
    lowest_addr = None
    highest_addr = None
    gaps = None
    contig_regions = None  # list of GuideRegion objects

    def __init__(self, kdamond_idx, context_idx, scheme_idx, tid, start_time):
        self.kdamond_idx = kdamond_idx
        self.context_idx = context_idx
        self.scheme_idx = scheme_idx
        self.tid = tid
        self.start_time = start_time
        self.gaps = []

    def regions(self):
        regions = []
        region = [self.lowest_addr]
        for gap in self.gaps:
            for idx, point in enumerate(gap):
                if idx == 0:
                    region.append(point)
                    regions.append(region)
                else:
                    region = [point]
        region.append(self.highest_addr)
        regions.append(region)
        return regions

    def total_space(self):
        ret = 0
        for r in self.regions():
            ret += r[1] - r[0]
        return ret

    def to_str(self, raw):
        lines = []
        if self.kdamond_idx is not None:
            lines.append('kdamond_idx: %s' % self.kdamond_idx)
        if self.context_idx is not None:
            line.sappend('context_idx: %s' % self.context_idx)
        if self.scheme_idx is not None:
            lines.append('scheme_idx: %s' % self.scheme_idx)
        if self.tid is not None:
            lines.append('target_id: %s' % self.tid)
        lines.append('time: [%s, %s) (%s)' % (
            _damo_fmt_str.format_time_ns(self.start_time, raw),
            _damo_fmt_str.format_time_ns(self.end_time, raw),
            _damo_fmt_str.format_time_ns(
                self.end_time - self.start_time, raw)))
        for idx, region in enumerate(self.contig_regions):
            lines.append('region\t%2d: [%s, %s) (%s)' % (
                idx,
                _damo_fmt_str.format_sz(region.start_addr, raw),
                _damo_fmt_str.format_sz(region.end_addr, raw),
                _damo_fmt_str.format_sz(
                    region.end_addr - region.start_addr, raw)))
        return '\n'.join(lines)

    def __str__(self):
        return self.to_str(raw=True)

def is_overlap(region1, region2):
    if region1[1] < region2[0]:
        return False
    if region2[1] < region1[0]:
        return False
    return True

def overlap_region_of(region1, region2):
    return [max(region1[0], region2[0]), min(region1[1], region2[1])]

def overlapping_regions(regions1, regions2):
    overlap_regions = []
    for r1 in regions1:
        for r2 in regions2:
            if is_overlap(r1, r2):
                r1 = overlap_region_of(r1, r2)
        if r1:
            overlap_regions.append(r1)
    return overlap_regions

def oldest_monitor_time(snapshot, record_intervals):
    if record_intervals is None:
        return snapshot.start_time
    longest_age = 0
    for region in snapshot.regions:
        if longest_age < region.age.aggr_intervals:
            longest_age = region.age.aggr_intervals
    aggr_interval_ns = record_intervals.aggr * 1000
    return snapshot.start_time - longest_age * aggr_interval_ns

def rec_to_guide_id(record):
    return '%s %s %s %s' % (record.kdamond_idx, record.context_idx,
                            record.scheme_idx, record.target_id)

def get_guide_info(records):
    "return the set of guide information for the moitoring result"
    guides = {}
    for record in records:
        guide_id = rec_to_guide_id(record)
        for snapshot in record.snapshots:
            if not guide_id in guides:
                guides[guide_id] = GuideInfo(
                        record.kdamond_idx, record.context_idx,
                        record.scheme_idx, record.target_id,
                        oldest_monitor_time(snapshot, record.intervals))
            guide = guides[guide_id]
            monitor_time = snapshot.end_time
            guide.end_time = monitor_time

            last_addr = None
            gaps = []
            for r in snapshot.regions:
                saddr = r.start
                eaddr = r.end

                if not guide.lowest_addr or saddr < guide.lowest_addr:
                    guide.lowest_addr = saddr
                if not guide.highest_addr or eaddr > guide.highest_addr:
                    guide.highest_addr = eaddr

                if not last_addr:
                    last_addr = eaddr
                    continue
                if last_addr != saddr:
                    gaps.append([last_addr, saddr])
                last_addr = eaddr

            if not guide.gaps:
                guide.gaps = gaps
            else:
                guide.gaps = overlapping_regions(guide.gaps, gaps)

    for guide_id, guide in guides.items():
        guide_regions = []
        for start, end in guide.regions():
            guide_regions.append(GuideRegion(start, end))
        guide.contig_regions = guide_regions

        for record in records:
            if rec_to_guide_id(record) != guide_id:
                continue
            for snapshot in record.snapshots:
                for region in snapshot.regions:
                    if region.nr_accesses.samples == 0:
                        continue
                    for gregion in guide.contig_regions:
                        if (region.end < gregion.start_addr or
                            gregion.end_addr < region.start):
                            continue
                        if gregion.heats is None:
                            gregion.heats = 0
                        gregion.heats += ((region.end - region.start) *
                                          region.nr_accesses.samples)

    return sorted(list(guides.values()), key=lambda x: x.total_space(),
                    reverse=True)

def pr_guide(records, raw_numbers=True):
    for guide in get_guide_info(records):
        print(guide.to_str(raw_numbers))

def main(args):
    records, err = _damo_records.get_records(record_file=args.input)
    if err != None:
        print('monitoring result file (%s) parsing failed (%s)' %
                (args.input, err))
        exit(1)
    pr_guide(records, args.raw_numbers)

def set_argparser(parser):
    parser.add_argument('--input', '-i', type=str, metavar='<file>', nargs='+',
            default='damon.data', help='input file name')
    parser.add_argument('--raw_numbers', action='store_true',
                        help='print numbers in raw format')
