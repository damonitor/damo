#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

damo="../../damo"

BINDIR=$(dirname "$0")
cd "$BINDIR" || exit 1

test_report() {
	cmd=$1
	test_name=$2

	expected=$(realpath "expects/report-$test_name")
	result=$(realpath "results/report-$test_name")

	eval "python3 $cmd" > "$result" 2> /dev/null
	if ! diff -q "$expected" "$result"
	then
		echo "FAIL report-$test_name"
		exit 1
	fi
	echo "PASS report-$test_name"
}

mkdir -p results

for filter in nofilter active inactive anon file unmapped hugepage
do
	for style in recency-percentiles temperature-percentiles \
		recency-sz-hist temperature-sz-hist detailed
	do
		test_cmd="$damo report access \
			--input damon.data.snapshot.$filter \
			--style $style"
		test_report "$test_cmd" "$style-$filter"
	done
done

damo_report_raw="$damo report access --raw_form --input"

test_report "$damo_report_raw damon.data" "raw"

test_report "$damo_report_raw damon.data.json_compressed" "raw"

test_report \
	"$damo_report_raw perf.data.script" \
	"raw_perf_script"

test_report "$damo report wss -r 1 101 1 --raw_number" "wss"

test_report "$damo report wss -r 1 101 1 --work_time 1000000 --raw_number" \
	"wss_worktime_1s"

test_report \
	"$damo adjust --aggregate_interval 1000000 && \
	$damo_report_raw damon.adjusted.data" \
	"aggr_1s_raw"

test_report \
	"$damo adjust --skip 30 --aggregate_interval 1000000 && \
	$damo_report_raw damon.adjusted.data" \
	"aggr_1s_raw_skip_30"

test_report "$damo report nr_regions -r 1 101 1" "nr_regions"

test_report "$damo report heatmap --guide" "heats_guide"

test_report "$damo report heatmap --output raw" "heats"

rm -fr results damon.adjusted.data

echo "PASS" "$(basename "$(pwd)")"
