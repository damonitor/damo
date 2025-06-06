# SPDX-License-Identifier: GPL-2.0

def idle_time(region):
    if region.nr_accesses.samples > 0:
        return 0
    return region.age.usec

def pr_percentile(percentile, idle_time_us):
    print('%3s %.3f'
          % (percentile, idle_time_us / 1000000))

def pr_idle_time_dist(regions, percentile_interval):
    regions = sorted(regions, key=lambda r: idle_time(r))
    total_sz = sum([r.size() for r in regions])
    if percentile_interval is None:
        percentiles_to_print = [0, 1, 25, 50, 75, 99]
    else:
        percentiles_to_print = list(range(0, 100, percentile_interval))
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
    if len(cmdline_fields) == 2:
        percentile_interval = int(cmdline_fields[1])
    else:
        percentile_interval = None
    for ridx, record in enumerate(records):
        for sidx, snapshot in enumerate(record.snapshots):
            print('# %d-th record, %d-th snapshot' % (ridx, sidx))
            print('# <memory size percentile> <idle time (seconds)>')
            for region in snapshot.regions:
                region.age.add_unset_unit(record.intervals)
            pr_idle_time_dist(snapshot.regions, percentile_interval)
