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
