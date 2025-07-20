#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

# This script shows example usage of damo for access-aware tiered memory
# management.  The script assumes the system has two NUMA nodes of id 0 and 1,
# and node 0 is faster than node 1, for all CPUs.  The script asks DAMON to
# migrate hot pages in node 1 to node 0 (promote), while migrating cold pages
# in node 0 to node 1 (demote).  The hotness and coldness thresholds are
# auto-tuned aiming ~99.6 percent of node 0 memory utilization.  The basic idea
# behind the tiering policy is came from TPP[1].  This script is also
# implemented for DAMON's auto-tune based memory tiering support[2].
#
# To run this, the kernel should have the auto-tuned memory tiering support of
# DAMON[2], which was landed into the mainline since v6.16-rc1.
#
# [1] https://dl.acm.org/doi/10.1145/3582016.3582063
# [2] https://lkml.kernel.org/r/20250420194030.75838-1-sj@kernel.org

set -e

bindir=$(realpath $(dirname "$0"))
damo_bin="$bindir/../damo"

if [ ! -f "$damo_bin" ]
then
	echo "damo not found at $damo_bin"
	exit 1
fi

"$damo_bin" module stat write enabled N
"$damo_bin" start \
	--numa_node 0 --monitoring_intervals_goal 4% 3 5ms 10s \
		--damos_action migrate_cold 1 --damos_access_rate 0% 0% \
		--damos_apply_interval 1s \
		--damos_quota_interval 1s --damos_quota_space 200MB \
		--damos_quota_goal node_mem_free_bp 0.5% 0 \
		--damos_filter reject young \
	--numa_node 1 --monitoring_intervals_goal 4% 3 5ms 10s \
		--damos_action migrate_hot 0 --damos_access_rate 5% max \
		--damos_apply_interval 1s \
		--damos_quota_interval 1s --damos_quota_space 200MB \
		--damos_quota_goal node_mem_used_bp 99.7% 0 \
		--damos_filter allow young \
		--damos_nr_quota_goals 1 1 --damos_nr_filters 1 1 \
	--nr_targets 1 1 --nr_schemes 1 1 --nr_ctxs 1 1
