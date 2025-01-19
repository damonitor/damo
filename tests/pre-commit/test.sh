#!/bin/bash

if ! which pre-commit &> /dev/null
then
	echo "pre-commit not installed. skip."
	exit 0
fi

if ! pre-commit run --all-file
then
	echo "FAIL pre-commit"
	exit 1
fi
echo "PASS pre-commit"
exit 0
