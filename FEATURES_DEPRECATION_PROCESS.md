As time goes by, some features are deprecated and removed.  To avoid
deprecations breaking users workflows, the process for the deprecation of
features are defined as below.

Deprecation Plan Notice
-----------------------

The plans to deprecate some features should be explicitly noticed.  The notice
should include by when it will be deprecated, and to where users can ask any
related questions including extension of the support.  That is, it should
include the grace period and ways to claim.  If applicable, the notice should
also include replacement of the feature.

The notice should be made on
[FEATURES_DEPRECATION_SCHEDULE.md](FEATURES_DEPRECATION_SCHEDULE.md) and
[USAGE.md](USAGE.md).  If avaialble, the notice should also be made on
execution of the features, and help messages that related to the features.  For
the notice on the execution, `will_be_deprecated()` of
`_damo_deprecation_notice.py` can be used.

If the feature is documented on [USAGE.md](USAGE.md) and not explicitly marked
as 'experimental feature' on the document, the deprecation schedule should
provide at least three months of the grace period.  In other cases, there is no
required minimum grace period.  That is, features can be immediately deprecated
if those are not documented on [USAGE.md](USAGE.md) or marked as experimental
on the document.  Users could ask specific features to be officially supported.


Deprecation
-----------

Once the grace period is passed and no users' special requests about it have
reported, the features are marked as deprecated.  The change should again be
noticed on
[FEATURES_DEPRECATION_SCHEDULE.md](FEATURES_DEPRECATION_SCHEDULE.md),
[USAGE.md](USAGE.md), execution output, and help messages as much as
possible.  For the notice on the execution, `deprecated()` of
`_damo_deprecation_notice.py` can be used.  The notice should include by when
the features will be entirely removed from the code base.  Unlike deprecations,
there is no required minimum grace period for removal of deprecated features.

Removal
-------

Once removal grace period is passed, related code can be removed from the
source tree.  If some of the source code is still required for testing purpose,
the code can be moved to `_damo_deprecated.py` file, and be used by the tests.
