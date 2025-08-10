# SPDX-License-Identifier: GPL-2.0

def idle_time(region):
    if region.nr_accesses.samples > 0:
        return 0
    return region.age.usec

def pr_idle_time_mem_sz(regions):
    regions = sorted(regions, key=lambda r: idle_time(r))
    total_sz = sum([r.size() for r in regions])
    max_idle_time = idle_time(regions[-1])
    min_idle_time = idle_time(regions[0])
    idle_time_interval = (max_idle_time - min_idle_time) / 100
    print('# idle time range: [%s, %s] seconds' % (
        min_idle_time / 1000000, max_idle_time / 1000000))
    print('# total memory size: %s bytes' % total_sz)

    count_max = min_idle_time + idle_time_interval
    while True:
        count_min = count_max - idle_time_interval
        sz = sum([r.size() for r in regions
                  if count_min <= idle_time(r) and idle_time(r) < count_max])
        if sz > 0:
            print('%f\t%f' % (count_max / 1000000, sz / total_sz * 100))
        if count_max > max_idle_time:
            break
        count_max += idle_time_interval

def main(records, cmdline_fields):
    for ridx, record in enumerate(records):
        for sidx, snapshot in enumerate(record.snapshots):
            print('# %d-th record, %d-th snapshot' % (ridx, sidx))
            print('# <idle time (seconds)> <memory size in percentage>')
            for region in snapshot.regions:
                region.age.add_unset_unit(record.intervals)
            pr_idle_time_mem_sz(snapshot.regions)
