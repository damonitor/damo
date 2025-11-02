# SPDX-License-Identifier: GPL-2.0

import json

import _damo_sysinfo
import _damon
import _damon_args
import _damon_sysfs

def pr_infer_version():
    if _damon._damon_fs is not _damon_sysfs:
        print('Version inference is unavailable')
        exit(1)

    sysinfo, err = _damo_sysinfo.get_sysinfo()
    if err is not None:
        print('getting sysinfo fail (%s)' % err)
        exit(1)
    avail_features = {f.name for f in sysinfo.avail_damon_sysfs_features}
    append_plus = False
    for feature in reversed(_damo_sysinfo.damon_features):
        if feature.name in avail_features:
            if feature.upstreamed_version in ['none', 'unknown']:
                append_plus = True
            else:
                version = feature.upstreamed_version
                if append_plus:
                    version = '%s+' % version
                print('Seems the version of DAMON is %s' % version)
                return

def main(args):
    if args.invalidate_cache:
        err = _damon.rm_feature_supports_file()
        if err is not None:
            print('invalidating cache fail (%s)' % err)
            exit(1)

    _damon.ensure_root_and_initialized(args)

    feature_supports, err = _damon.get_feature_supports()
    if err != None:
        print('getting feature supports info failed (%s)' % err)
        exit(1)
    for feature in sorted(feature_supports.keys()):
        supported = feature_supports[feature]
        if args.type == 'all':
            print('%s: %s' % (feature,
                'Supported' if supported else 'Unsupported'))
        elif args.type == 'supported' and supported:
            print(feature)
        elif args.type == 'unsupported' and not supported:
            print(feature)
    if args.type == 'json':
        print(json.dumps(feature_supports, indent=4, sort_keys=True))

    if args.infer_version:
        pr_infer_version()

def set_argparser(parser):
    parser.add_argument('type', nargs='?',
            choices=['supported', 'unsupported', 'all', 'json'], default='all',
            help='type of features to listed')
    parser.add_argument('--infer_version', action='store_true',
                        help='infer version of DAMON')
    parser.add_argument('--invalidate_cache', action='store_true',
                        help='check features again, from the scratch')
    _damon_args.set_common_argparser(parser)
