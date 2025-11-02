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

if __name__ == '__main__':
    unittest.main()
