#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import unittest

import _test_damo_common

_test_damo_common.add_damo_dir_to_syspath()

import _damo_sysinfo

class TestDamoSysinfo(unittest.TestCase):
    def test_damon_feature_kvpair_conversion(self):
        f = _damo_sysinfo.DamonFeature(
                name='foo', upstream_status='bar', comments='baz')
        kvpairs = f.to_kvpairs()
        f2 = _damo_sysinfo.DamonFeature.from_kvpairs(kvpairs)
        self.assertEqual(f, f2)

    def test_systeminfo_kvpair_conversion(self):
        features = []
        for i in range(4):
            features.append(_damo_sysinfo.DamonFeature(
                name='foo %s' % i, upstream_status='bar %s' % i,
                comments='baz %s' % i))
        sinfo = _damo_sysinfo.SystemInfo(
                damo_version='v3.1.1',
                kernel_version='6.18.0-rc2-mm-new-damon+',
                avail_damon_sysfs_features=[f for f in features[:2]],
                avail_damon_debugfs_features=[f for f in features[2:]])
        kvpairs = sinfo.to_kvpairs()
        sinfo2 = _damo_sysinfo.SystemInfo.from_kvpairs(kvpairs)
        self.assertEqual(sinfo, sinfo2)

if __name__ == '__main__':
    unittest.main()
