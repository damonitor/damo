#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

bindir=$(dirname "$0")
cd "$bindir" || exit 1

restart_damon_stat="false"
damon_stat_enabled_file="/sys/module/damon_stat/parameters/enabled"
if [ $(cat "$damon_stat_enabled_file") = "Y" ]
then
	echo "DAMON_STAT is running.  Disable for testing."
	echo N > "$damon_stat_enabled_file"
	restart_damon_stat="true"
fi

for test_dir in unit pre-commit record report schemes \
	damon_reclaim damon_lru_sort start_stop
do
	if ! "./$test_dir/test.sh"
	then
		if [ "$restart_damon_stat" = "true" ]
		then
			echo Y > "$damon_stat_enabled_file"
		fi
		exit 1
	fi
done

if [ "$restart_damon_stat" = "true" ]
then
	echo Y > "$damon_stat_enabled_file"
fi

echo "PASS ALL"
