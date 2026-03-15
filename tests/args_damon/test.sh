#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

bindir=$(dirname "$0")
cd "$bindir"

testname=$(basename $(pwd))

for script in lru_sort.sh mem_tier.sh weighted_interleave.sh
do
	if ! sudo bash "./${script}" > /dev/null
	then
		echo "FAIL $testname $script"
		exit 1
	fi
	echo "PASS $testname $script"
done
echo "PASS $testname"
