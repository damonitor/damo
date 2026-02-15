# SPDX-License-Identifier: GPL-2.0

import collections

class DamonFeature:
    name = None
    upstream_status = None
    upstreamed_version = None
    comments = None

    def __init__(self, name, upstream_status, upstreamed_version='unknown',
                 comments=''):
        self.name = name
        self.upstream_status = upstream_status
        self.upstreamed_version = upstreamed_version
        self.comments = comments

    def to_kvpairs(self, raw=False):
        return collections.OrderedDict([
            ('name', self.name),
            ('upstream_status', self.upstream_status),
            ('upstreamed_version', self.upstreamed_version),
            ('comments', self.comments),
            ])

    @classmethod
    def from_kvpairs(cls, kvpairs):
        if 'upstreamed_version' in kvpairs:
            upstreamed_version = kvpairs['upstreamed_version']
        else:
            upstreamed_version = 'unknown'
        return cls(kvpairs['name'], kvpairs['upstream_status'],
                   upstreamed_version,
                   kvpairs['comments'])

    def __eq__(self, other):
        return self.name == other.name and \
                self.upstream_status == other.upstream_status and \
                self.upstreamed_version == other.upstreamed_version and \
                self.comments == other.comments

# naming convention: interface/<interface> and <interface>/<feature>
# <interface>:
# - damon_debugfs
# - damon_reclaim
# - damon_sysfs
# - damon_lru_sort
# - damon_stat
# - damon_sysfs
#
# features should be sorted by upstreamed time
features_list = [
        # v5.15-rc1 release: Sun Sep 12 16:28:37 2021 -0700
        DamonFeature(
            name='debugfs/record', upstream_status='withdrawn',
            upstreamed_version='none',
            comments='was in DAMON patchset, but not merged in mainline'),
        DamonFeature(name='debugfs/vaddr', upstream_status='merged in v5.15',
                     upstreamed_version='5.15'),
        DamonFeature(name='trace/damon_aggregated',
                      upstream_status='merged in v5.15 (2fcb93629ad8)',
                      upstreamed_version='5.15'),
        DamonFeature(name='interface/damon_debugfs',
                     upstream_status='merged in v5.15-rc1 (4bc05954d007)',
                     upstreamed_version='5.15'),

        # v5.16-rc1 release: Sun Nov 14 13:56:52 2021 -0800
        DamonFeature(name='debugfs/schemes', upstream_status='merged in v5.16',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/init_regions',
                     upstream_status='merged in v5.16 (90bebce9fcd6)',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/paddr',
                     upstream_status='merged in v5.16 (a28397beb55b)',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/schemes_size_quota',
                     upstream_status='merged in v5.16 (2b8a248d5873)',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/schemes_time_quota',
                     upstream_status='merged in v5.16 (1cd243030059)',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/schemes_prioritization',
                     upstream_status='merged in v5.16 (38683e003153)',
                     upstreamed_version='5.16'),
        DamonFeature(name='debugfs/schemes_wmarks',
                     upstream_status='merged in v5.16 (ee801b7dd782)',
                     upstreamed_version='5.16'),
        DamonFeature(name='interface/damon_reclaim',
                     upstream_status='merged in v5.16-rc1 (43b0536cb471)',
                     upstreamed_version='5.16'),

        # v5.17-rc1 release: Sun Jan 23 10:12:53 2022 +0200
        DamonFeature(name='debugfs/schemes_stat_succ',
                     upstream_status='merged in v5.17 (0e92c2ee9f45)',
                     upstreamed_version='5.17'),
        DamonFeature(name='debugfs/schemes_stat_qt_exceed',
                     upstream_status='merged in v5.17 (0e92c2ee9f45)',
                     upstreamed_version='5.17'),
        DamonFeature(name='reclaim/stats',
                     upstream_status='merged in v5.17-rc1 (0e92c2ee9f45)',
                     upstreamed_version='5.17'),

        # v5.18-rc1 release: Sun Apr 3 14:08:21 2022 -0700
        DamonFeature(name='debugfs/init_regions_target_idx',
                     upstream_status='merged in v5.18 (144760f8e0c3)',
                     upstreamed_version='5.18'),
        DamonFeature(name='interface/damon_sysfs',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/vaddr',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_time_quota',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/paddr',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/init_regions',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_stat_succ',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_size_quota',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_stat_qt_exceed',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_wmarks',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),
        DamonFeature(name='sysfs/schemes_prioritization',
                     upstream_status='merged in v5.18-rc1 (c951cd3b8901)',
                     upstreamed_version='5.18'),

        # v5.19-rc1 release: Sun Jun 5 17:18:54 2022 -0700
        DamonFeature(name='sysfs/avail_ops',
                     upstream_status='merged in v5.19 (0f2cb5885771b)',
                     upstreamed_version='5.19'),
        DamonFeature(name='sysfs/fvaddr',
                     upstream_status='merged in v5.19 (b82434471cd2)',
                     upstreamed_version='5.19'),
        DamonFeature(name='sysfs/online_params_commit',
                     upstream_status='merged in v5.19 (adc286e6bdd3)',
                     upstreamed_version='5.19'),
        DamonFeature(name='reclaim/commit_inputs',
                     upstream_status='merged in v5.19 (81a84182c3430)',
                     upstreamed_version='5.19'),

        #v6.0-rc1 release: Sun Aug 14 15:50:18 2022 -0700
        DamonFeature(name='interface/damon_lru_sort',
                     upstream_status='merged in v6.0-rc1 (40e983cca927)',
                     upstreamed_version='6.0'),

        # v6.1-rc1 release: Sun Oct 16 15:36:24 2022 -0700
        # v6.2-rc1 release: Sun Dec 25 13:41:39 2022 -0800
        DamonFeature(name='sysfs/schemes_tried_regions',
                     upstream_status='merged in v6.2-rc1',
                     upstreamed_version='6.2'),

        # v6.3-rc1 release: Sun Mar 5 14:52:03 2023 -0800
        DamonFeature(name='sysfs/schemes_filters',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='sysfs/schemes_filters_anon',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='sysfs/schemes_filters_memcg',
                     upstream_status='merged in v6.3-rc1',
                     upstreamed_version='6.3'),
        DamonFeature(name='reclaim/skip_anon',
                     upstream_status='merged in v6.3-rc1 (d56fe24237c3d)',
                     upstreamed_version='6.3'),

        # v6.4-rc1 release: Sun May 7 13:34:35 2023 -0700
        # v6.5-rc1 release: Sun Jul 9 13:53:13 2023 -0700
        # v6.6-rc1 release: Sun Sep 10 16:28:41 2023 -0700
        DamonFeature(name='sysfs/schemes_tried_regions_sz',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),
        DamonFeature(name='sysfs/schemes_filters_addr',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),
        DamonFeature(name='sysfs/schemes_filters_target',
                     upstream_status='merged in v6.6-rc1',
                     upstreamed_version='6.6'),

        # v6.7-rc1 release: Sun Nov 12 16:19:07 2023 -0800
        DamonFeature(name='sysfs/schemes_apply_interval',
                     upstream_status='merged in v6.7-rc1',
                     upstreamed_version='6.7'),
        DamonFeature(name='trace/damos_before_apply',
                     upstream_status='merged in v6.7-rc1 (c603c630b509)',
                     upstreamed_version='6.7'),

        # v6.8-rc1 release: Sun Jan 21 14:11:32 2024 -0800
        DamonFeature(name='sysfs/schemes_quota_goals',
                     upstream_status='merged in v6.8-rc1',
                     upstreamed_version='6.8'),

        # v6.9-rc1 release: Sun Mar 24 14:10:05 2024 -0700
        DamonFeature(name='sysfs/schemes_quota_effective_bytes',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='sysfs/schemes_quota_goal_metric',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='sysfs/schemes_quota_goal_some_psi',
                     upstream_status='merged in v6.9-rc1',
                     upstreamed_version='6.9'),
        DamonFeature(name='reclaim/quota_mem_pressure_us',
                     upstream_status='merged in v6.9-rc1 (75c40c2509e79)',
                     upstreamed_version='6.9'),
        DamonFeature(name='reclaim/quota_user_feedback',
                     upstream_status='merged in v6.9-rc1 (75c40c2509e79)',
                     upstreamed_version='6.9'),

        # v6.10-rc1 release: Sun May 26 15:20:12 2024 -0700
        DamonFeature(name='sysfs/schemes_filters_young',
                     upstream_status='merged in v6.10-rc1',
                     upstreamed_version='6.10'),

        # v6.11-rc1 release: Sun Jul 28 14:19:55 2024 -0700
        DamonFeature(name='sysfs/schemes_migrate',
                     upstream_status='merged in v6.11-rc1',
                     upstreamed_version='6.11'),

        # v6.12-rc1 release: Sun Sep 29 15:06:19 2024 -0700
        # v6.13-rc1 release: Sun Dec 1 14:28:56 2024 -0800
        # v6.14-rc1 release: Sun Feb 2 15:39:26 2025 -0800
        DamonFeature(name='sysfs/sz_ops_filter_passed',
                     upstream_status='merged in v6.14-rc1',
                     upstreamed_version='6.14'),
        DamonFeature(name='sysfs/allow_filter',
                     upstream_status='merged in v6.14-rc1',
                     upstreamed_version='6.14'),

        # v6.15-rc1 release: Sun Apr 6 13:11:33 2025 -0700
        DamonFeature(name='sysfs/schemes_filters_hugepage_size',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='sysfs/schemes_filters_unmapped',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='sysfs/intervals_goal',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='sysfs/schemes_filters_core_ops_dirs',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),
        DamonFeature(name='sysfs/schemes_filters_active',
                     upstream_status='merged in v6.15-rc1',
                     upstreamed_version='6.15'),

        # v6.16-rc1 release: Sun Jun 8 13:44:43 2025 -0700
        DamonFeature(name='sysfs/schemes_quota_goal_node_mem_used_free',
                     upstream_status='merged in v6.16-rc1',
                     upstreamed_version='6.16'),

        # v6.17-rc1 release: Sun Aug 10 19:41:16 2025 +0300
        DamonFeature(name='sysfs/schemes_dests',
                     upstream_status='merged in v6.17-rc1',
                     upstreamed_version='6.17'),
        DamonFeature(name='sysfs/refresh_ms',
                     upstream_status='merged in v6.17-rc1',
                     upstreamed_version='6.17'),
        DamonFeature(name='trace/damon_monitor_intervals_tune',
                     upstream_status='merged in v6.17-rc1 (214db7028727)',
                     upstreamed_version='6.17'),
        DamonFeature(name='trace/damos_esz',
                     upstream_status='merged in v6.17-rc1 (a86d695193bf)',
                     upstreamed_version='6.17'),
        DamonFeature(name='interface/damon_stat',
                     upstream_status='merged in v6.17-rc1 (369c415e6073)',
                     upstreamed_version='6.17'),

        # v6.18-rc1 release: Sun Oct 12 13:42:36 2025 -0700
        DamonFeature(name='sysfs/addr_unit',
                     upstream_status='merged in v6.18-rc1',
                     upstreamed_version='6.18'),
        DamonFeature(name='reclaim/addr_unit',
                     upstream_status='merged in v6.18-rc1 (7db551fcfb2a)',
                     upstreamed_version='6.18'),
        DamonFeature(name='lru_sort/addr_unit',
                     upstream_status='merged in v6.18-rc1 (2e0fe9245d6b)',
                     upstreamed_version='6.18'),
        DamonFeature(name='stat/aggr_interval',
                     upstream_status='merged in v6.18-rc1 (cc7ceb1d14b0)',
                     upstreamed_version='6.18'),
        DamonFeature(name='stat/negative_idle_time',
                     upstream_status='merged in v6.18-rc1 (a983a26d5298)',
                     upstreamed_version='6.18'),

        # v6.19-rc1 release: Sun Dec 14 16:05:07 2025 +1200
        DamonFeature(name='sysfs/schemes_quota_goal_node_memcg_used_free',
                     upstream_status='merged in v6.19-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='sysfs/obsolete_target',
                     upstream_status='merged in v6.19-rc1',
                     upstreamed_version='none'),

        DamonFeature(name='sysfs/damos_stat_nr_snapshots',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='sysfs/damos_max_nr_snapshots',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='trace/damos_stat_after_apply_interval',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='sysfs/damos_quota_goal_in_active_mem_bp',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='lru_sort/young_page_filter',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='lru_sort/active_mem_bp',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),
        DamonFeature(name='lru_sort/autotune_monitoring_intervals',
                     upstream_status='merged in mm, expected for 6.20/7.0-rc1',
                     upstreamed_version='none'),

        DamonFeature(name='sysfs/damon_sample_control',
                     upstream_status='hacking on damon/next',
                     upstreamed_version='none',
                     comments='a replacement of ops_attrs'),
        DamonFeature(name='sysfs/ops_attrs',
                     upstream_status='hacking on damon/next',
                     upstreamed_version='none'),
        ]

def feature_of_name(name):
    return [f for f in features_list if f.name == name][0]
