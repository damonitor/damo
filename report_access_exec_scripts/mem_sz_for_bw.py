# SPDX-License-Identifier: GPL-2.0

'''
Show how much memory is required to fulfill how much of memory bandwidth
consumption.
'''

import math

def bw_consumption(region):
    'Return estimated bandwidth consumption of the region'
    return region.size() * region.nr_accesses.samples

def pr_membw_memsz_percentile(snapshot):
    total_bw_consumption = sum([bw_consumption(r) for r in snapshot.regions])
    if total_bw_consumption == 0:
        print('zero bw')
        return
    # sort regiosn to hot regions come first, since we try to find minimum size
    # of memory that can serve specific portion of the workload's memory
    # bandwidth consumption
    sorted_regions = sorted(snapshot.regions,
                            key=lambda r: r.nr_accesses.samples, reverse=True)
    total_sz = sum([r.size() for r in snapshot.regions])

    next_percentile_to_print = 1
    bw_cumulated = 0
    sz_cumulated = 0
    print('<bw percent>\t<mem sz percent>')
    print(' '.join([
        '<mem sz percent> % of memory is required to serve',
        '<bw percent> % of bandwidth consumption']))
    for r in sorted_regions:
        bw_cumulated += bw_consumption(r)
        sz_cumulated += r.size()
        # todo: split region to show exact bw percentile numbers
        if bw_cumulated / total_bw_consumption * 100 < next_percentile_to_print:
            continue
        print('%.2f\t%.2f' %
              (bw_cumulated / total_bw_consumption * 100, sz_cumulated /
               total_sz * 100))
        next_percentile_to_print = math.floor(bw_cumulated /
                                              total_bw_consumption * 100 + 5)
    
def main(records, cmdline_fields):
    for ridx, record in enumerate(records):
        print('%d-th record' % ridx)
        for sidx, snapshot in enumerate(record.snapshots):
            print('%d-th snapshot' % sidx)
            pr_membw_memsz_percentile(snapshot)
