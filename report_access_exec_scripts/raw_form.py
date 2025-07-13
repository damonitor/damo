# SPDX-License-Identifier: GPL-2.0

def main(records, cmdline_fields):
    for ridx, record in enumerate(records):
        print('%d-th record' % ridx)
        print('intervals: %d %d' %
              (record.intervals.sample, record.intervals.aggr))
        for sidx, snapshot in enumerate(record.snapshots):
            print('%d-th snapshot' % sidx)
            print('snapshot sample interval: %d' % snapshot.sample_interval_us)
            for region in snapshot.regions:
                print('%s-%s (%s): %s %s' % (
                    region.start, region.end, region.size(),
                    region.nr_accesses.sample, region.age.aggr_intervals))
