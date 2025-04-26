# SPDX-License-Identifier: GPL-2.0

def idle_time(region):
    if region.nr_accesses.samples > 0:
        return 0
    return region.age.aggr_intervals

def pr_percentile(percentile, val):
    print('%18s %20s'
          % ('%d-th percentile:' % percentile, val))

def pr_idle_time_dist(regions):
    regions = sorted(regions, key=lambda r: idle_time(r))
    total_sz = sum([r.size() for r in regions])
    pr_percentile(0, idle_time(regions[0]))
    percentiles_to_print = [1, 25, 50, 75, 99]
    percentile = 0
    for r in regions:
        percentile += r.size() * 100 / total_sz
        while len(percentiles_to_print) > 0:
            if percentile < percentiles_to_print[0]:
                break
            pr_percentile(percentiles_to_print[0], idle_time(r))
            percentiles_to_print = percentiles_to_print[1:]
    pr_percentile(100, idle_time(regions[-1]))

def main(records, cmdline_fields):
    for ridx, record in enumerate(records):
        for sidx, snapshot in enumerate(record.snapshots):
            print('%d-th record, %d-th snapshot' % (ridx, sidx))
            pr_idle_time_dist(snapshot.regions)
