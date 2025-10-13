#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

bindir=$(dirname "$0")
cd "$bindir"

damo="../../damo"

cmd_log=$(mktemp damo_test_cmd_log_XXX)

cleanup_files()
{
	files_to_remove="./damon.data ./damon.data.perf.data ./damon.data.old"
	for file in $files_to_remove
	do
		if [ -f "$file" ]
		then
			if ! sudo rm "$file"
			then
				echo "removing $file failed"
				exit 1
			fi
		fi
	done
}

test_record_permission()
{
	sudo "$damo" record "sleep 5" --timeout 5 --output_permission 611 \
		&> "$cmd_log"
	if [ ! "$(stat -c %a damon.data)" = "611" ]
	then
		echo "FAIL record-permission"
		cat "$cmd_log"
		exit 1
	fi
	cleanup_files

	echo "PASS record-permission"
}

test_record_validate()
{
	if [ $# -ne 4 ]
	then
		echo "Usage: $0 <target> <timeout> <region> \\"
		echo "		<damon interface to use>"
		exit 1
	fi

	target=$1
	timeout=$2
	regions_boundary=$3
	damon_interface=$4

	testname="record-validate \"$target\" $timeout $regions_boundary"
	testname+=" $damon_interface"

	if [ "$target" = "paddr" ] && ! sudo "$damo" features \
		--damon_interface_DEPRECATED "$damon_interface" supported \
		2> /dev/null | \
		grep -w paddr &> /dev/null
	then
		echo "SKIP record-validate $target $timeout (paddr unsupported)"
		return
	fi

	if [ "$regions_boundary" = "none" ]
	then
		sudo "$damo" record "$target" --timeout "$timeout" \
			--damon_interface_DEPRECATED "$damon_interface" \
			&> "$cmd_log"
	else
		sudo "$damo" record "$target" --timeout "$timeout" \
			--regions "$regions_boundary" \
			--damon_interface_DEPRECATED "$damon_interface" \
			&> "$cmd_log"
	fi

	rc=$?
	if [ $rc -ne 0 ]
	then
		echo "FAIL $testname"
		echo "(damo-record command failed with value $rc)"
		cat "$cmd_log"
		exit 1
	fi

	if [ "$regions_boundary" = "none" ]
	then
		if ! sudo "$damo" validate &> "$cmd_log"
		then
			echo "FAIL $testname (record file is not valid)"
			cat "$cmd_log"
			exit 1
		fi
	else
		if ! sudo "$damo" validate \
			--regions_boundary "$regions_boundary" &> "$cmd_log"
		then
			echo "FAIL $testname (record file is not valid)"
			cat "$cmd_log"
			exit 1
		fi
	fi

	if [ -f ./damon.data.perf.data ]
	then
		echo "FAIL $testname (perf.data is not removed)"
		cat "$cmd_log"
		exit 1
	fi

	permission=$(stat -c %a damon.data)
	if [ ! "$permission" = "600" ]
	then
		echo "FAIL $testname (out file permission $permission)"
		cat "$cmd_log"
		exit 1
	fi

	cleanup_files

	echo "PASS $testname"
}

damon_interfaces=""
if [ -d "/sys/kernel/debug/damon" ]
then
	damon_interfaces+="debugfs "
fi

if [ -d "/sys/kernel/mm/damon" ]
then
	damon_interfaces+="sysfs "
fi

if [ "$damon_interfaces" = "" ]
then
	echo "SKIP $(basename $(pwd)) (DAMON interface not found)"
	exit 0
fi

for damon_interface in $damon_interfaces
do
	test_record_validate "sleep 5" 5 "none" "$damon_interface"
	test_record_validate "paddr" 3 "none" "$damon_interface"
done

if sudo "$damo" features \
	--damon_interface_DEPRECATED "$damon_interface" supported \
	2> /dev/null | \
	grep -w fvaddr &> /dev/null
then
	test_record_validate "sleep 5" 5 "4096-81920" "sysfs"
fi

test_record_permission

rm -f "$cmd_log"
echo "PASS $(basename $(pwd))"
