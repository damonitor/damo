#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

# This script shows example usage of damo for access-aware weighted
# interleaving. The script assumes the system has two NUMA nodes of id 0 and 1.
# The script asks DAMON to interleave hot pages of the target process, passed
# as the first command line argument of this script, at a 1:1 ratio between
# nodes 0 and 1. 
#
# To run this, the kernel should have the weighted interleaving support of
# DAMON[1], which is expected to land into mainline in v6.17-rc1.
#
# [1] https://lore.kernel.org/r/20250709005952.17776-1-bijan311@gmail.com/

set -e

bindir=$(realpath $(dirname "$0"))
damo_bin="$bindir/../damo"
target_proc=$1

if [ ! -f "$damo_bin" ]
then
	echo "damo not found at $damo_bin"
	exit 1
fi

"$damo_bin" start \
	--target_pid $target_proc --ops vaddr \
		--monitoring_intervals_goal 4% 3 5ms 10s \
		--damos_action migrate_hot 0 1 1 1 --damos_access_rate 5% max \
		--damos_apply_interval 1s \
		--damos_quota_interval 1s --damos_quota_space 200MB \
