#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

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
