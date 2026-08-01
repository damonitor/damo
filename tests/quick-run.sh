#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

# Run a set of quick tests.  Recommended to set as post-commit hook.
# Run run.sh for full tests.

set -e

bindir=$(dirname "$0")

"$bindir/flake8.sh"
"$bindir/pre-commit/test.sh"
"$bindir/unit/test.sh"
