# SPDX-License-Identifier: GPL-2.0

'''
Print size of memory in DAMON monitoring results that was idle (not accessed)
for given time interval.

For example,

    $ ./damo report access \
            --exec ./report_access_exec_scripts/mem_sz_per_idle_time.py \
            --input_file damon.data
    # 0-th record, 0-th snapshot
    # idle time range: [0.0, 1338.06458] seconds
    # total memory size: 66571956224 bytes
    # <idle time (seconds)> <memory size in percentage>
    13.380646       44.658132
    26.761292       5.001520
    40.141937       12.840912
    107.045166      17.645280
    120.425812      5.067533
    200.709687      0.003150
    267.612916      0.015769
    307.754853      0.031502
    441.561311      0.003150
    521.845186      3.189839
    682.412936      0.078730
    1003.548435     9.578593
    1351.445226     1.885889

The output can be interpreted as below.

    # idle time range: [0.0, 1338.06458] seconds

The above line of the output says the minimum and maximum idle time of regions
that captured by DAMON and stored in 'damon.data' file are 0 second (the idle
time of the hottest region) and 1338.06 seconds (the idle time of the coldest
region).

    # total memory size: 66571956224 bytes

The above line of the output says the snapshot is capturing the access pattern
of about 61 GiB memory.

    13.380646       44.658132

The above line of the output can be interpreted as 44.658 % of the monitored
memory (about 27.68 GiB) was not accessed for [0, 13.38) seconds.

    13.380646       44.658132
    26.761292       5.001520

Above two lines of the output can be interpreted as 5.001 % of the monitored
memory (about 3.10 GiB) was not accessed for [13.38, 26.76) seconds.

    1003.548435     9.578593
    1351.445226     1.885889

Above two lines of the output can be interpreted as 1.885 % of the monitored
memory (about 1.16 GiB) was not accessed for [1003,54, 1351.44) seconds.

Note that the length of the idle time range is defined as 1/100 of difference
between maximum and minimum idle time of the snpashot, and the output for zero
memory size are skipped.  In the above example, the maximum and minimum idle
time of the snapshot were 0 seconds and 1338.06 seconds, so the idle time range
for each output line is about 13.38 seconds.  Hence, more accurate
interpretation of the last line of the output (1351.445226     1.885889) is
that 1.885 % of the monitored memory (about 1.16 GiB) was not acessed for
[1338.06, 1351.445) seconds.
'''

def idle_time(region):
    if region.nr_accesses.samples > 0:
        return 0
    return region.age.usec

def pr_idle_time_mem_sz(regions, pr_zero_size):
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
        if sz > 0 or pr_zero_size is True:
            print('%f\t%f' % (count_max / 1000000, sz / total_sz * 100))
        if count_max > max_idle_time:
            break
        count_max += idle_time_interval

def main(records, cmdline_fields):
    if '--pr_zero_size' in cmdline_fields:
        pr_zero_size = True
    else:
        pr_zero_size = False
    for ridx, record in enumerate(records):
        for sidx, snapshot in enumerate(record.snapshots):
            print('# %d-th record, %d-th snapshot' % (ridx, sidx))
            print('# <idle time (seconds)> <memory size in percentage>')
            for region in snapshot.regions:
                region.age.add_unset_unit(record.intervals)
            pr_idle_time_mem_sz(snapshot.regions, pr_zero_size)
