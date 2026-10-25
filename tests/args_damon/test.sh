#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

bindir=$(dirname "$0")
cd "$bindir"

testname=$(basename $(pwd))

for script in test_*.sh
do
	if ! sudo bash "./${script}" &> output
	then
		echo "FAIL $testname $script"
		exit 1
	fi
	expect_name=$(echo "$script" | awk -F "test_" '{print $2}' | \
		awk -F ".sh" '{print $1}')
	if ! diff -u output "output_expects/${expect_name}"
	then
		echo "FAIL $testname $script diff"
		exit 1
	fi
	rm output
	echo "PASS $testname $script"
done
echo "PASS $testname"
