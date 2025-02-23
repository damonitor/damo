# SPDX-License-Identifier: GPL-2.0

import argparse
import os

import _damo_fmt_str
import _damon

class PaddrRange:
    start = None
    end = None
    nid = None
    state = None
    name = None

    def __init__(self, start, end, nid, state, name):
        self.start = start
        self.end = end
        self.nid = nid
        self.state = state
        self.name = name

    def __str__(self):
        return '%x-%x, nid %s, state %s, name %s' % (self.start, self.end,
                self.nid, self.state, self.name)

class MemBlock:
    nid = None
    index = None
    state = None

    def __init__(self, nid, index, state):
        self.nid = nid
        self.index = index
        self.state = state

    def __str__(self):
        return '%d (%s)' % (self.index, self.state)

    def __repr__(self):
        return self.__str__()

def readfile(file_path):
    with open(file_path, 'r') as f:
        return f.read()

def collapse_ranges(ranges):
    ranges = sorted(ranges, key=lambda x: x.start)
    merged = []
    for r in ranges:
        if not merged:
            merged.append(r)
            continue
        last = merged[-1]
        if last.end != r.start or last.nid != r.nid or last.state != r.state:
            merged.append(r)
        else:
            last.end = r.end
    return merged

def memblocks_to_ranges(blocks, block_size):
    ranges = []
    for b in blocks:
        ranges.append(PaddrRange(b.index * block_size,
            (b.index + 1) * block_size, b.nid, b.state, None))

    return collapse_ranges(ranges)

def memblock_ranges():
    SYSFS='/sys/devices/system/node'
    sz_block = int(readfile('/sys/devices/system/memory/block_size_bytes'), 16)
    sys_nodes = [x for x in os.listdir(SYSFS) if x.startswith('node')]

    blocks = []
    for sys_node in sys_nodes:
        nid = int(sys_node[4:])

        sys_node_files = os.listdir(os.path.join(SYSFS, sys_node))
        for f in sys_node_files:
            if not f.startswith('memory'):
                continue
            if f[6:] == '_failure':
                continue
            index = int(f[6:])
            sys_state = os.path.join(SYSFS, sys_node, f, 'state')
            state = readfile(sys_state).strip()

            blocks.append(MemBlock(nid, index, state))

    return memblocks_to_ranges(blocks, sz_block)

def iomem_ranges():
    ranges = []

    with open('/proc/iomem', 'r') as f:
        # example of the line: '100000000-42b201fff : System RAM'
        for line in f:
            fields = line.split(':')
            if len(fields) < 2:
                continue
            name = ':'.join(fields[1:]).strip()
            addrs = fields[0].split('-')
            if len(addrs) != 2:
                continue
            start = int(addrs[0], 16)
            end = int(addrs[1], 16) + 1
            ranges.append(PaddrRange(start, end, None, None, name))

    return ranges

def integrate(memblock_parsed, iomem_parsed):
    merged = []

    for r in iomem_parsed:
        for r2 in memblock_parsed:
            if r2.start <= r.start and r.end <= r2.end:
                r.nid = r2.nid
                r.state = r2.state
                merged.append(r)
            elif r2.start <= r.start and r.start < r2.end and r2.end < r.end:
                sub = PaddrRange(r2.end, r.end, None, None, r.name)
                iomem_parsed.append(sub)
                r.end = r2.end
                r.nid = r2.nid
                r.state = r2.state
                merged.append(r)
    merged = sorted(merged, key=lambda x: x.start)
    return merged

def paddr_ranges():
    return integrate(memblock_ranges(), iomem_ranges())

def pr_ranges(ranges, raw):
    print('#%14s %14s\tnode\tstate\tresource\tsize' % ('start', 'end'))
    for r in ranges:
        print('%15s %15s\t%s\t%s\t%s\t%s' % (
            _damo_fmt_str.format_sz(r.start, raw),
            _damo_fmt_str.format_sz(r.end, raw),
            _damo_fmt_str.format_nr(r.nid, raw),
            r.state, r.name,
            _damo_fmt_str.format_sz(r.end - r.start, raw)))

def default_paddr_region():
    "Largest System RAM region becomes the default"
    ret = []
    with open('/proc/iomem', 'r') as f:
        # example of the line: '100000000-42b201fff : System RAM'
        for line in f:
            fields = line.split(':')
            if len(fields) != 2:
                continue
            name = fields[1].strip()
            if not name.startswith('System RAM'):
                continue
            addrs = fields[0].split('-')
            if len(addrs) != 2:
                continue
            start = int(addrs[0], 16)
            end = int(addrs[1], 16)

            sz_region = end - start
            if not ret or sz_region > (ret[1] - ret[0]):
                ret = [start, end]
    return ret

def paddr_region_of(numa_node):
    if not os.path.isdir('/sys/devices/system/memory'):
        return None, '/sys/devices/system/memory not found.  You may need CONFIG_MEMORY_HOTPLUG enabled.'

    regions = []
    paddr_ranges_ = paddr_ranges()
    for r in paddr_ranges_:
        if r.nid == numa_node and r.name.startswith('System RAM'):
            if len(regions) > 0 and regions[-1][1] == r.start:
                regions[-1][1] = r.end
                continue
            regions.append([r.start, r.end])
    return regions, None

def numa_addr_ranges(nodes):
    if not os.path.isdir('/sys/devices/system/memory'):
        return None, ' '.join([
            '/sys/devices/system/memory not found.',
            'You may need CONFIG_MEMORY_HOTPLUG enabled.'])

    ranges = []
    for node in nodes:
        node_ranges, err = paddr_region_of(node)
        if err is not None:
            return None, err
        if len(ranges) > 0 and len(node_ranges) > 0:
            last_range = ranges[-1]
            new_first_range = node_ranges[0]
            if last_range[1] == new_first_range[0]:
                last_range[1] = new_first_range[1]
            node_ranges = node_ranges[1:]
        ranges += node_ranges
    return ranges, None

def main(args):
    _damon.ensure_root_permission()

    if args.numa_addr is not None:
        ranges, err = numa_addr_ranges([args.numa_addr])
        if err is not None:
            print(err)
            return 1
        for start, end in ranges:
            print('[%s, %s) (size %s)' % (
                _damo_fmt_str.format_sz(start, args.raw_number),
                _damo_fmt_str.format_sz(end, args.raw_number),
                _damo_fmt_str.format_sz(end - start, args.raw_number)))
        return

    ranges = []
    for r in paddr_ranges():
        if args.numa_node and r.nid != args.numa_node:
            continue
        ranges.append(r)

    pr_ranges(ranges, args.raw_number)

    start, end = default_paddr_region()
    print('largest system RAM region: [%s, %s) (size %s)' % (
        _damo_fmt_str.format_sz(start, args.raw_number),
        _damo_fmt_str.format_sz(end, args.raw_number),
        _damo_fmt_str.format_sz(end - start, args.raw_number)))

def set_argparser(parser):
    parser.description = 'Show physical address space layout'
    parser.add_argument('--numa_node', type=int, metavar='<node id>',
            help='print ranges of this numa node only')
    parser.add_argument('--numa_addr', type=int, metavar='<node id>',
                        help='show only address ranges of the numa node')
    parser.add_argument('--raw_number', action='store_true',
                        help='use machine-friendly raw numbers')
