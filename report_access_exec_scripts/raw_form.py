# SPDX-License-Identifier: GPL-2.0

def main(records, cmdline_fields):
    for ridx, record in enumerate(records):
        print('%d-th record' % ridx)
        for sidx, snapshot in enumerate(record.snapshots):
            print('%d-th snapshot' % sidx)
            for region in snapshot.regions:
                print('%s-%s (%s): %s %s' % (
                    region.start, region.end, region.size(),
                    region.nr_accesses.percent, region.age.usec))
