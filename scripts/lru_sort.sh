#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

# This script shows example usage of damo for access-aware Linux kernel LRU
# lists sorting[1,2].  This script asks DAMON to move hot and cold pages in
# active and inactive LRU lists to inactive and active lists, respectively.
# The hotness and coldness thresholds are automatically tuned by DAMON, aiming
# number of pages in active LRU lists and inactive LRU lists being nearly same.
#
# To run this, the kernel should run with the LRU sorting advancing patch
# series[2], which is not yet merged into the mainline as of this writing
# (2025-07-20).
#
# [1] https://lwn.net/Articles/905370/
# [2] https://lore.kernel.org/20250628165144.55528-1-sj@kernel.org

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
	--monitoring_intervals_goal 4% 3 5ms 10s \
		--damos_action lru_deprio --damos_access_rate 0% 0% \
			--damos_apply_interval 1s \
			--damos_quota_interval 1s --damos_quota_space 100MB \
			--damos_quota_goal inactive_mem_bp 50.1% \
			--damos_quota_weights 0 1 1 \
			--damos_filter reject young \
		--damos_action lru_prio --damos_access_rate 5% max \
			--damos_apply_interval 1s \
			--damos_quota_interval 1s --damos_quota_space 100MB \
			--damos_quota_goal active_mem_bp 50.1% \
			--damos_quota_weights 0 1 1 \
			--damos_filter allow young \
	--damos_nr_quota_goals 1 1 --damos_nr_filters 1 1
