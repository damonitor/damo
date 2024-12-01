Deprecated, or Will be Deprecated Features
==========================================

Below are features that deprecated, or will be deprecated.  If you depend on
any of those, please [report](REPORTING.md).

`damo report raw`
-----------------

Will be deprecated by 2025-01-27.  Use `damo report access --raw_form' instead.


`damo show`, `damo status`
--------------------------

Will be deprecated by 2025-01-20.  Use `damo report access` and `damo report
damon` instead.

`DAMON` and `damo` were initially designed with offline recording-based usages.
Therefore `damo record` and `damo report` were the main subcommands.  Later,
`DAMON` has evolved for more online usages, and therefore `damo` was also
developed for support of online "snapshot" based usages.  For taking
"snapshots" of the monitoring results and DAMON status, we implemented separate
subcommands, namely `show` and `status`.  The new features work well, but makes
the number of `damo` subcommands bit unnecessarily high, and make usages
confusing.

We therefore extended `record` and `report` to further support online
"snapshot" based workflows.  As of this writing, `report access` and `report
damon` can replace all features of `show` and `status`.  Hence we decided to
deprecate `show` and `status`.


`damo report heats`
-------------------

Will be dperecated by 2025-01-20.  Use `damo report heatmap` instead.


`damo fmt_json`
---------------

Deprecated.  Will be removed by 2024-12.  Use `damo args damon --format json`
instead.


`--damon_interface`
-------------------

Deprecated.  Use `--damon_interface_DEPRECATED` instead.

DAMON provides two major user interfaces, namely 'DAMON debugfs' and 'DAMON
sysfs' interfaces.  `damo` subcommands for DAMON control such as `start`,
`stop`, `tune` therefore provided `--damon_interface` option to allow selection
of the interface.  That's mostly for testing purpose, not for real users.  Also
DAMON debugfs interface is deprecated in Linux kernel.  Hence
`--damon_interface` is deprecated, and replaced by
`--damon_interface_DEPRECATED`.  `--damon_interface_DEPRECTED` will also be
deprecated and removed soon.


`damo translate_damos`
----------------------

Deprecated.  Use the command of v2.0.2 or lower version of DAMO instead.


DAMON record binary format
--------------------------

Deprecated.  Use `json_compressed` format instead.

At the beginning, DAMO used its special binary format, namely `record`.  It is
designed for lightweight saving of the monitoring results.  It is difficult to
read, and not that efficient compared to fancy compression techniques.  `json`
based monitoring results can be easier to read, and more efficient when
compression technique is used.  Hence, the format is deprecated.  You may
use `damo convert_record_format` of v2.0.2 or lower version of DAMO to convert
your old record binary format monitoring results files to the new format.


Python2 support
---------------

Deprecated.  Use Python3.

For some old distros, DAMO initially supported Python2.  Because Python2 is
really old now, the support has deprecated.  Please use Python3 or newer.


DAMOS single line format
------------------------

Deprecated.  Use `--damos_*` command line options or json format input.

A simple DAMOS scheme specification format called one-line scheme specification
was initially supported.  Because it is not flexible for extension of features,
it has deprecated now.  You may use `--damos_*` command line options or json
format instead.  You could use `damo translate_damos` ov v2.0.2 or lower
version of DAMO to convert your old single line DAMOS schemes specification to
the new json format.


--rbuf option of `damo record`
------------------------------

Deprecated.

Early versions of DAMON supported in-kernel direct monitoring results record
file generation.  To control the overhead of it, DAMO allowed user to specify
the size of buffer for the work.  The feature has not merged into the mainline,
and discarded.  Hence the option was available for only few kernels that ported
the feature.  For most of kernels, tracepoint based record file generation is
being used, and the overhead of the approach is subtle.  Hence, the option has
deprecated.
