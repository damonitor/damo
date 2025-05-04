# SPDX-License-Identifier: GPL-2.0

"""
Command line arguments handling
"""

import argparse
import json
import os
import subprocess

# for non-python-default modules
try:
    import yaml
except ModuleNotFoundError as e:
    # do nothing.  The yaml using functions should handle the exception
    # properly.
    pass

import _damo_subproc
import _damon
import damo_pa_layout

# Kdamonds construction from command line arguments

def range_overlap_or_contig(range1, range2):
    s1, e1 = range1
    s2, e2 = range2
    if e1 == s2 or e2 == s1:
        return True
    if e1 <= s2:
        return False
    if e2 <= s1:
        return False
    return True

def merge_ranges(ranges):
    ranges.sort(key=lambda r: r[0])
    merged_ranges = []
    for start, end in ranges:
        if len(merged_ranges) > 0 and range_overlap_or_contig(
                merged_ranges[-1], [start, end]):
            merged_ranges[-1] = [min(merged_ranges[-1][0], start),
                                 max(merged_ranges[-1][1], end)]
        else:
            merged_ranges.append([start, end])
    return merged_ranges

def init_regions_for(args_regions, args_ops, args_numa_node):
    init_regions = []
    if args_regions:
        for region in args_regions.split():
            addrs = region.split('-')
            try:
                if len(addrs) != 2:
                    raise Exception ('two addresses not given')
                region = _damon.DamonRegion(addrs[0], addrs[1])
                if region.start >= region.end:
                    raise Exception('start >= end')
                if init_regions and init_regions[-1].end > region.start:
                    raise Exception('regions overlap')
            except Exception as e:
                return None, 'Wrong \'--regions\' argument (%s)' % e
            init_regions.append(region)

    if args_ops == 'paddr' and not init_regions:
        if args_numa_node != None:
            init_regions, err = damo_pa_layout.numa_addr_ranges(
                    args_numa_node)
            if err != None:
                return None, err
            init_regions = merge_ranges(init_regions)
        else:
            init_regions = [damo_pa_layout.default_paddr_region()]
        try:
            init_regions = [_damon.DamonRegion(r[0], r[1])
                    for r in init_regions]
        except Exception as e:
            return None, 'Wrong \'--regions\' argument (%s)' % e

    return init_regions, None

def override_vals(to_override, new_vals):
    if new_vals is None:
        return
    for idx, new_val in enumerate(new_vals):
        if new_val is not None:
            to_override[idx] = new_val

def damon_intervals_for(args_intervals, args_sample, args_aggr, args_updr,
                        args_intervals_goal):
    intervals = ['5ms', '100ms', '1s']
    override_vals(intervals, args_intervals)
    override_vals(intervals, [args_sample, args_aggr, args_updr])

    if args_intervals_goal is None:
        args_intervals_goal = ['0%', '0', '0us', '0us']

    intervals_goal = _damon.DamonIntervalsGoal(*args_intervals_goal)

    return _damon.DamonIntervals(*intervals, intervals_goal)

def damon_nr_regions_range_for(args_range, args_minr, args_maxr):
    nr_range = ['10', '1000']
    override_vals(nr_range, args_range)
    override_vals(nr_range, [args_minr, args_maxr])
    return _damon.DamonNrRegionsRange(*nr_range)

def schemes_option_to_damos(schemes):
    if os.path.isfile(schemes):
        with open(schemes, 'r') as f:
            schemes = f.read()

    try:
        kvpairs = json.loads(schemes)
        return [_damon.Damos.from_kvpairs(kv) for kv in kvpairs], None
    except Exception as json_err:
        return None, '%s' % json_err

def damos_filter_with_optional_args(ftype, fmatching, allow, optional_words):
    # return filter, error, and number of consumed words
    if ftype == 'memcg':
        if len(optional_words) < 1:
            return None, 'no memcg path is given', 0
        memcg_path = optional_words[0]
        return _damon.DamosFilter(ftype, fmatching, memcg_path=memcg_path,
                                  allow=allow), None, 1
    if ftype == 'addr':
        if len(optional_words) < 2:
            return None, 'no address range is given', 0
        try:
            addr_range = _damon.DamonRegion(optional_words[0], optional_words[1])
        except Exception as e:
            return None, 'wrong addr range (%s, %s)' % (optional_words, e), 0
        return _damon.DamosFilter(ftype, fmatching, allow=allow,
                                  address_range=addr_range), None, 2
    elif ftype == 'target':
        if len(optional_words) < 1:
            return None, 'no target argument', 0
        try:
            return _damon.DamosFilter(
                    ftype, fmatching, allow=allow,
                    damon_target_idx=optional_words[0]), None, 1
        except Exception as e:
            return None, 'target filter creation failed (%s, %s)' % (
                    optional_words[0], e), 0
    elif ftype == 'hugepage_size':
        if len(optional_words) < 2:
            return None, 'no range for hugepage sizes is given', 0
        hugepage_size = [optional_words[0], optional_words[1]]
        return _damon.DamosFilter(ftype, fmatching, allow=allow,
                                  hugepage_size=hugepage_size), None, 2

    return None, 'unsupported filter type', 0

def damos_options_to_filter_v2(words):
    '''
    Returns filter, error, and consumed number of words
    '''
    if len(words) < 2:
        return None, 'wrong number of words: %s' % words, 0
    if not words[0] in ['allow', 'reject', 'deny', 'block']:
        return None, 'unsupported allow-reject idntifier: %s' % words[0], 0
    allow = words[0] == 'allow'
    nr_consumed_words = 1
    word = words[nr_consumed_words]
    if word == 'none':
        fmatching = False
        nr_consumed_words += 1
    else:
        fmatching = True
    ftype = words[nr_consumed_words]
    nr_consumed_words += 1

    if ftype in ['anon', 'active', 'young', 'unmapped']:
        filter = _damon.DamosFilter(ftype, fmatching, allow=allow)
        return filter, None, nr_consumed_words
    else:
        filter, err, nr_words = damos_filter_with_optional_args(
                ftype, fmatching, allow, words[nr_consumed_words:])
        if err is not None:
            return None, 'handling %s fail (%s)' % (words, err), 0
        return filter, None, nr_consumed_words + nr_words

def damos_options_to_filters_v2(words):
    filters = []
    while len(words) > 0:
        filter, err, nr_consumed_words = damos_options_to_filter_v2(words)
        if err is not None:
            return None, err
        filters.append(filter)
        words = words[nr_consumed_words:]
    return filters, None

def convert_damos_filter_v1_to_v2(filter_args):
    if len(filter_args) < 2:
        return None, '<2 filter argument'
    filter_type = filter_args[0]
    matching = filter_args[1] == 'matching'
    optional_args = filter_args[2:]
    if len(optional_args) == 0:
        allow_reject = 'reject'
    else:
        if optional_args[-1] in ['allow', 'pass', 'reject', 'deny', 'block']:
            if optional_args[-1] in ['allow', 'pass']:
                allow_reject = 'allow'
            else:
                allow_reject = 'reject'
            optional_args = optional_args[:-1]
        else:
            allow_reject = 'reject'
    v2_args = [allow_reject]
    if matching is False:
        v2_args.append('none')
    return v2_args + [filter_type] + optional_args, None

def damos_options_to_filters(filters_args):
    filters = []
    if filters_args == None:
        return filters, None

    full_words = []
    for fields in filters_args:
        full_words += fields
    filters, v2_err = damos_options_to_filters_v2(full_words)
    if v2_err is None:
        return filters, None

    full_words = []
    for filter_args in filters_args:
        converted_filter_args, err = convert_damos_filter_v1_to_v2(filter_args)
        if err is not None:
            return None, 'converting format fail (%s, %s)' % (filter_args, err)
        full_words += converted_filter_args

    filters, v2_err = damos_options_to_filters_v2(full_words)
    return filters, v2_err

def damos_quotas_cons_arg(cmd_args):
    time_ms = 0
    sz_bytes = 0
    reset_interval_ms = 'max'
    weights = ['0 %', '0 %', '0 %']

    nr_cmd_args = len(cmd_args)
    if nr_cmd_args >= 1:
        time_ms = cmd_args[0]
    if nr_cmd_args >= 2:
        sz_bytes = cmd_args[1]
    if nr_cmd_args >= 3:
        reset_interval_ms = cmd_args[2]
    if nr_cmd_args >= 4:
        weights[0] = cmd_args[3]
    if nr_cmd_args >= 5:
        weights[1] = cmd_args[4]
    if nr_cmd_args >= 6:
        weights[2] = cmd_args[5]

    return [time_ms, sz_bytes, reset_interval_ms, weights]

def damos_options_to_quota_goal(garg):
    # garg is the user inputs
    # garg should be <metric> <target value> [<current value>|<nid>]
    # [current value] is given for only 'user_input' <metric>
    # [nid] is given for only node_mem_{used,free}_bp
    if not len(garg) in [2, 3]:
        return None, 'Wrong --damos_quota_goal (%s)' % garg
    metric, target_value, optionals = garg[0], garg[1], garg[2:]
    current_value = 0
    nid = None
    if _damon.DamosQuotaGoal.metric_require_nid(metric):
        if len(optionals) != 1:
            return None, 'nid is not given or something else is given'
        nid = optionals[0]
    elif metric == 'user_input':
        if len(optionals) != 1:
            return None, 'current value is not given or something else is given'
        current_value = optionals[0]
    try:
        return _damon.DamosQuotaGoal(
                metric=metric, target_value=target_value,
                current_value=current_value, nid=nid), None
    except Exception as e:
        return None, 'DamosQuotaGoal creation fail (%s, %s)' % (garg, e)

def damos_options_to_quotas(quotas, goals):
    gargs = goals
    goals = []
    for garg in gargs:
        goal, err = damos_options_to_quota_goal(garg)
        if err is not None:
            return None, 'quota goals parsing fail (%s)' % err
        goals.append(goal)

    qargs = quotas
    if len(qargs) > 6:
        return None, 'Wrong --damos_quotas (%s, >6 parameters)' % qargs
    try:
        quotas = _damon.DamosQuotas(*damos_quotas_cons_arg(qargs),
                                    goals=goals)
    except Exception as e:
        return None, 'Wrong --damos_quotas (%s, %s)' % (qargs, e)
    return quotas, None

def damos_options_to_scheme(sz_region, access_rate, age, action,
        apply_interval, quotas, goals, wmarks, target_nid, filters):
    if quotas != None:
        quotas, err = damos_options_to_quotas(quotas, goals)
        if err is not None:
            return None, err

    if wmarks != None:
        wargs = wmarks
        try:
            wmarks = _damon.DamosWatermarks(wargs[0], wargs[1], wargs[2],
                    wargs[3], wargs[4])
        except Exception as e:
            return None, 'Wrong --damos_wmarks (%s, %s)' % (wargs, e)

    filters, err = damos_options_to_filters(filters)
    if err != None:
        return None, err

    try:
        return _damon.Damos(
                access_pattern=_damon.DamosAccessPattern(sz_region,
                    access_rate, _damon.unit_percent, age, _damon.unit_usec),
                action=action, target_nid=target_nid,
                apply_interval_us=apply_interval, quotas=quotas,
                watermarks=wmarks, filters=filters), None
    except Exception as e:
        return None, 'Wrong \'--damos_*\' argument (%s)' % e

def damos_options_to_schemes(args):
    if args.damos_quota_interval:
        for i, interval in enumerate(args.damos_quota_interval):
            t, s = 0, 0
            if i < len(args.damos_quota_time):
                t = args.damos_quota_time[i]
            if i < len(args.damos_quota_space):
                s = args.damos_quota_space[i]
            if i < len(args.damos_quota_weights):
                w1, w2, w3 = args.damos_quota_weights[i]
            else:
                w1, w2, w3 = 1, 1, 1
            args.damos_quotas.append([t, s, interval, w1, w2, w3])
    nr_schemes = len(args.damos_action)
    if len(args.damos_sz_region) > nr_schemes:
        return [], 'too much --damos_sz_region'
    if len(args.damos_access_rate) > nr_schemes:
        return [], 'too much --damos_access_rate'
    if len(args.damos_age) > nr_schemes:
        return [], 'too much --damos_age'
    if len(args.damos_apply_interval) > nr_schemes:
        return [], 'too much --damos_apply_interval'
    if len(args.damos_quotas) > nr_schemes:
        return [], 'too much --damos_quotas'
    if len(args.damos_quota_goal) > 0 and nr_schemes > 1:
        if len(args.damos_nr_quota_goals) == 0:
            return [], '--damos_nr_quota_goals required'
    if nr_schemes == 1 and args.damos_nr_quota_goals == []:
        args.damos_nr_quota_goals = [len(args.damos_quota_goal)]
    if sum(args.damos_nr_quota_goals) != len(args.damos_quota_goal):
        return [], 'wrong --damos_nr_quota_goals'
    if len(args.damos_wmarks) > nr_schemes:
        return [], 'too much --damos_wmarks'
    # for multiple schemes, number of filters per scheme is required
    if len(args.damos_filter) > 0 and nr_schemes > 1:
        if len(args.damos_nr_filters) == 0:
            return [], '--damos_nr_filters required'
    if nr_schemes == 1 and args.damos_nr_filters == []:
        args.damos_nr_filters = [len(args.damos_filter)]
    if sum(args.damos_nr_filters) != len(args.damos_filter):
        return [], 'wrong --damos_nr_filters'

    args.damos_sz_region += [['min', 'max']] * (
            nr_schemes - len(args.damos_sz_region))
    args.damos_access_rate += [['min', 'max']] * (
            nr_schemes - len(args.damos_access_rate))
    args.damos_age += [['min', 'max']] * (nr_schemes - len(args.damos_age))
    args.damos_apply_interval += [0] * (
            nr_schemes - len(args.damos_apply_interval))
    args.damos_quotas += [None] * (nr_schemes - len(args.damos_quotas))
    args.damos_wmarks += [None] * (nr_schemes - len(args.damos_wmarks))
    target_nid = [None] * nr_schemes
    schemes = []

    for i in range(nr_schemes):
        action = args.damos_action[i][0]
        if _damon.is_damos_migrate_action(action):
            try:
                target_nid[i] = int(args.damos_action[i][1])
                args.damos_action[i] = args.damos_action[i][0]
            except:
                return [], '"%s" action require a numeric target_nid argument.' \
                            % args.damos_action[i][0]
        else:
            args.damos_action[i] = action

        qgoals = []
        if args.damos_quota_goal:
            goal_start_index = sum(args.damos_nr_quota_goals[:i])
            goal_end_index = goal_start_index + args.damos_nr_quota_goals[i]
            qgoals = args.damos_quota_goal[goal_start_index:goal_end_index]

        filters = []
        if args.damos_filter:
            filter_start_index = sum(args.damos_nr_filters[:i])
            filter_end_index = filter_start_index + args.damos_nr_filters[i]
            filters = args.damos_filter[filter_start_index:filter_end_index]
        scheme, err = damos_options_to_scheme(args.damos_sz_region[i],
                args.damos_access_rate[i], args.damos_age[i],
                args.damos_action[i], args.damos_apply_interval[i],
                args.damos_quotas[i], qgoals, args.damos_wmarks[i], target_nid[i], filters)
        if err != None:
            return [], err
        schemes.append(scheme)
    return schemes, None

def damos_for(args):
    if args.damos_action:
        schemes, err = damos_options_to_schemes(args)
        if err != None:
            return None, err
        return schemes, None

    if not 'schemes' in args or args.schemes == None:
        return [], None

    schemes, err = schemes_option_to_damos(args.schemes)
    if err:
        return None, 'failed damo schemes arguments parsing (%s)' % err
    return schemes, None

def damon_target_for(args, idx, ops):
    init_regions, err = init_regions_for(
            args.regions[idx], ops, args.numa_node[idx])
    if err:
        return None, err

    try:
        target = _damon.DamonTarget(args.target_pid[idx]
                if _damon.target_has_pid(ops) else None, init_regions)
    except Exception as e:
        return 'Wrong \'--target_pid\' argument (%s)' % e
    return target, None

def damon_ctx_for(args, idx):
    if args.ops[idx] is None:
        if args.target_pid[idx] is None:
            args.ops[idx] = 'paddr'
        else:
            args.ops[idx] = 'vaddr'

    try:
        intervals = damon_intervals_for(
                args.monitoring_intervals[idx], args.sample[idx],
                args.aggr[idx], args.updr[idx],
                args.monitoring_intervals_goal[idx])
    except Exception as e:
        return None, 'invalid intervals arguments (%s)' % e
    try:
        nr_regions = damon_nr_regions_range_for(
                args.monitoring_nr_regions_range[idx],
                args.minr[idx], args.maxr[idx])
    except Exception as e:
        return None, 'invalid nr_regions arguments (%s)' % e
    ops = args.ops[idx]

    try:
        ctx = _damon.DamonCtx(ops, None, intervals, nr_regions, schemes=[],
                              addr_unit=args.ops_addr_unit)
        return ctx, None
    except Exception as e:
        return None, 'Creating context from arguments failed (%s)' % e

def get_nr_ctxs(args):
    candidates = []
    for v in [args.ops, args.sample, args.aggr, args.updr, args.minr,
              args.maxr, args.monitoring_intervals,
              args.monitoring_intervals_goal,
              args.monitoring_nr_regions_range]:
        if v is not None:
            candidates.append(len(v))
    if args.nr_targets is not None:
        candidates.append(len(args.nr_targets))
    if args.nr_schemes is not None:
        candidates.append(len(args.nr_schemes))
    if len(candidates) == 0:
        return 1
    return max(candidates)

def get_nr_targets(args):
    candidates = []
    for v in [args.target_pid, args.regions, args.numa_node]:
        if v is not None:
            candidates.append(len(v))
    candidates.append(get_nr_ctxs(args))
    return max(candidates)

def fillup_none_ctx_args(args):
    nr_ctxs = get_nr_ctxs(args)
    for attr_name in [
            'ops', 'sample', 'aggr', 'updr', 'minr', 'maxr',
            'monitoring_intervals', 'monitoring_intervals_goal',
            'monitoring_nr_regions_range']:
        attr_val = getattr(args, attr_name)
        if attr_val is None:
            setattr(args, attr_name, [None] * nr_ctxs)
        elif len(attr_val) < nr_ctxs:
            print(attr_name, attr_val)
            setattr(args, attr_name,
                    attr_val + [None] * (nr_ctxs - len(attr_val)))

def fillup_none_target_args(args):
    nr_targets = get_nr_targets(args)
    for attr_name in ['target_pid', 'regions', 'numa_node']:
        attr_val = getattr(args, attr_name)
        if attr_val is None:
            setattr(args, attr_name, [None] * nr_targets)
        elif len(attr_val) < nr_targets:
            print(attr_name, attr_val)
            setattr(args, attr_name,
                    attr_val + [None] * (nr_targets - len(attr_val)))

def gen_assign_targets(ctxs, args):
    nr_targets = get_nr_targets(args)
    targets = []
    if args.nr_targets is None:
        if len(ctxs) != 1:
            return '--nr_targets is required for multiple contexts'
        args.nr_targets = [nr_targets]
    for idx in range(nr_targets):
        for i in range(len(args.nr_targets)):
            if idx < sum(args.nr_targets[:i + 1]):
                ops = args.ops[i]
                break
        target, err = damon_target_for(args, idx, ops)
        if err is not None:
            return None, err
        targets.append(target)
    if sum(args.nr_targets) != len(targets):
        return '--nr_targets and number of targets mismatch (%d != %d)' % (
                sum(args.nr_targets), len(targets))
    if len(args.nr_targets) != len(ctxs):
        return '--nr_targets and number of ctxs mismatch (%d != %d)' % (
                len(args.nr_targets), len(ctxs))
    ctx_idx = 0
    target_idx = 0
    for nr in args.nr_targets:
        ctxs[ctx_idx].targets = targets[target_idx:target_idx + nr]
        ctx_idx += 1
        target_idx += nr
    return None

def gen_assign_schemes(ctxs, args):
    schemes, err = damos_for(args)
    if err is not None:
        return err
    if args.nr_schemes is None:
        if len(ctxs) != 1 and len(schemes) > 0:
            return '--nr_schemes is required for multiple contexts'
        args.nr_schemes = [len(schemes)]
        args.nr_schemes += [0] * (len(ctxs) - 1)
    if sum(args.nr_schemes) != len(schemes):
        return '--nr_schemes and number of schemes mismatch (%d != %d)' % (
                sum(args.nr_schemes), len(schemes))
    if len(args.nr_schemes) != len(ctxs):
        return '--nr_schemes and number of ctxs mismatch (%d != %d)' % (
                len(args.nr_schemes), len(ctxs))
    ctx_idx = 0
    scheme_idx = 0
    for nr in args.nr_schemes:
        ctxs[ctx_idx].schemes = schemes[scheme_idx:scheme_idx + nr]
        ctx_idx += 1
        scheme_idx += nr
    return None

def damon_ctxs_for(args):
    fillup_none_ctx_args(args)
    fillup_none_target_args(args)
    ctxs = []
    for idx in range(get_nr_ctxs(args)):
        ctx, err = damon_ctx_for(args, idx)
        if err is not None:
            return None, err
        ctxs.append(ctx)

    err = gen_assign_targets(ctxs, args)
    if err is not None:
        return None, err

    err = gen_assign_schemes(ctxs, args)
    if err is not None:
        return None, err

    return ctxs, err

def kdamonds_from_json_arg(arg):
    try:
        if os.path.isfile(arg):
            with open(arg, 'r') as f:
                kdamonds_str = f.read()
        else:
            kdamonds_str = arg
        kdamonds_kvpairs = json.loads(kdamonds_str)['kdamonds']
        return [_damon.Kdamond.from_kvpairs(kvp)
                for kvp in kdamonds_kvpairs], None
    except Exception as e:
        return None, e

def kdamonds_from_yaml_arg(arg):
    try:
        assert os.path.isfile(arg)
        with open(arg, 'r') as f:
            kdamonds_str = f.read()
        kdamonds_kvpairs = yaml.safe_load(kdamonds_str)['kdamonds']
        return [_damon.Kdamond.from_kvpairs(kvp)
                for kvp in kdamonds_kvpairs], None
    except Exception as e:
        return None, e

target_type_explicit = 'explicit'
target_type_cmd = 'cmd'
target_type_pid = 'pid'
target_type_unknown = None

def deduced_target_type(target):
    if target in ['vaddr', 'paddr', 'fvaddr']:
        return target_type_explicit
    if _damo_subproc.avail_cmd(target.split()[0]):
        return target_type_cmd
    else:
        pass
    try:
        pid = int(target)
        return target_type_pid
    except:
        pass
    return target_type_unknown

def warn_option_override(option_name):
    print('warning: %s is overridden by <deducible target>' % option_name)

def deduce_target_update_args(args):
    'deducible target supports only single context/single kdamond'
    args.self_started_target = False
    target_type = deduced_target_type(args.deducible_target)
    if target_type == target_type_unknown:
        return 'target \'%s\' is not supported' % args.deducible_target
    if target_type == target_type_explicit and args.deducible_target == 'paddr':
        if not args.ops in [['paddr'], None]:
            warn_option_override('--ops')
        args.ops = ['paddr']
        if args.target_pid != None:
            warn_option_override('--target_pid')
        args.target_pid = None
        return None
    if target_type == target_type_cmd:
        p = subprocess.Popen(args.deducible_target, shell=True,
                executable='/bin/bash')
        pid = p.pid
        args.self_started_target = True
    elif target_type == target_type_pid:
        pid = int(args.deducible_target)
    if args.target_pid != None:
        print('warning: --target_pid will be ignored')
    args.target_pid = [pid]
    if not args.regions:
        if not args.ops in [['vaddr'], None]:
            warn_option_override('--ops')
        args.ops = ['vaddr']
    if args.regions:
        if not args.ops in [['fvaddr'], None]:
            print('warning: override --ops by <deducible target> and --regions')
        args.ops = ['fvaddr']

def evaluate_args(args):
    '''
    Verify if 'damons_action' is present when any 'damos_*' is specified
    '''
    if not args.damos_action:
        for key, value in args.__dict__.items():
            if key.startswith('damos_') and len(value):
                if key == 'damos_action': continue
                return False, '\'damos_action\' not specified while using --damos_* option(s)'

    if len(args.damos_quotas) > 0 and len(args.damos_quota_interval) > 0:
        return False, '--damos_quotas and --damos_quota_interval cannot passed together'

    '''
    Verify if 'reset_interval_ms' is specified in args when setting quota goals
    '''
    if args.damos_quota_goal:
        damos_quotas = args.damos_quotas

        if not len(damos_quotas) and not len(args.damos_quota_interval):
            return False, '\'reset_interval_ms\' not specified when setting quota goals'

        #reset_interval_ms is specified in --damos_quotas as 3rd arg
        for quota in damos_quotas:
            if len(quota) < 3:
                return False, '\'reset_interval_ms\' not specified when setting quota goals'

    return True, None

def kdamonds_for(args):
    correct, err = evaluate_args(args)
    if err is not None:
        return None, err

    if args.kdamonds:
        return kdamonds_from_json_arg(args.kdamonds)

    if args.deducible_target:
        if args.deducible_target.endswith('.yaml'):
            kdamonds, e = kdamonds_from_yaml_arg(args.deducible_target)
        else:
            kdamonds, e = kdamonds_from_json_arg(args.deducible_target)
        if e == None:
            return kdamonds, e
        err = deduce_target_update_args(args)
        if err:
            return None, err

    ctxs, err = damon_ctxs_for(args)
    if err:
        return None, err

    if args.nr_ctxs is None:
        args.nr_ctxs = [len(ctxs)]
    if sum(args.nr_ctxs) != len(ctxs):
        return None, '--nr_ctxs and number of ctxs mismatch (%d != %d)' % (
                sum(args.nr_ctxs), len(ctxs))

    kdamonds = []
    ctx_idx = 0
    for nr in args.nr_ctxs:
        try:
            kdamonds.append(_damon.Kdamond(
                state=None, pid=None, contexts=ctxs[ctx_idx:ctx_idx + nr]))
        except Exception as e:
            return None, 'kdamond creation fail (%s)' % e
        ctx_idx += nr
    return kdamonds, None

def self_started_target(args):
    return 'self_started_target' in args and args.self_started_target

# Command line processing helpers

def is_ongoing_target(args):
    return args.deducible_target == 'ongoing'

def stage_kdamonds(args):
    kdamonds, err = kdamonds_for(args)
    if err:
        return None, 'cannot create kdamonds from args (%s)' % err
    err = _damon.stage_kdamonds(kdamonds)
    if err:
        return None, 'cannot apply kdamonds from args (%s)' % err
    return kdamonds, None

def commit_kdamonds(args, commit_quota_goals_only):
    kdamonds, err = kdamonds_for(args)
    if err:
        return None, 'cannot create kdamonds to commit from args (%s)' % err
    err = _damon.commit(kdamonds, commit_quota_goals_only)
    if err:
        return None, 'cannot commit kdamonds (%s)' % err
    return kdamonds, None

def turn_damon_on(args):
    kdamonds, err = stage_kdamonds(args)
    if err:
        return err, None
    return _damon.turn_damon_on(
            ['%s' % kidx for kidx, k in enumerate(kdamonds)]), kdamonds

# Commandline options setup helpers

def set_common_argparser(parser):
    parser.add_argument('--damon_interface_DEPRECATED',
            choices=['sysfs', 'debugfs', 'auto'],
            default='auto',
            # underlying DAMON interface to use (!! DEPRECATED)
            help=argparse.SUPPRESS)
    parser.add_argument('--debug_damon', action='store_true',
            help='Print debugging log')

def set_monitoring_attrs_pinpoint_argparser(parser, hide_help=False):
    # for easier pinpoint setup
    parser.add_argument(
            '-s', '--sample', metavar='<microseconds>', action='append',
            help='sampling interval (us)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '-a', '--aggr', metavar='<microseconds>', action='append',
            help='aggregate interval (us)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '-u', '--updr', metavar='<microseconds>', action='append',
            help='regions update interval (us)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '-n', '--minr', metavar='<# regions>', action='append',
            help='minimal number of regions'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '-m', '--maxr', metavar='<# regions>', action='append',
            help='maximum number of regions'
            if not hide_help else argparse.SUPPRESS)

def set_monitoring_attrs_argparser(parser, hide_help=False):
    # for easier total setup
    parser.add_argument('--monitoring_intervals', nargs=3, action='append',
                        metavar=('<sample>', '<aggr>', '<update>'),
                        help='monitoring intervals (us)'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--monitoring_intervals_goal', nargs=4, action='append',
            metavar=('<access_bp>', '<aggrs>', '<min_sample_us>',
                     '<max_sample_us>'),
            help='monitoring intervals auto-tuning goal'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--monitoring_nr_regions_range', nargs=2,
                        metavar=('<min>', '<max>'), action='append',
                        help='min/max number of monitoring regions'
                        if not hide_help else argparse.SUPPRESS)

def set_monitoring_argparser(parser, hide_help=False):
    parser.add_argument('--ops', choices=['vaddr', 'paddr', 'fvaddr'],
                        action='append',
                        help='monitoring operations set'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--ops_addr_unit', metavar='<bytes>',
                        help='operations set address unit'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--target_pid', type=int, metavar='<pid>',
                        action='append',
                        help='pid of monitoring target process'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('-r', '--regions', metavar='"<start>-<end> ..."',
                        type=str, action='append',
                        help='monitoring target address regions'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--numa_node', metavar='<node id>', type=int, nargs='+',
            action='append',
            help='if target is \'paddr\', limit it to the numa node'
            if not hide_help else argparse.SUPPRESS)
    set_monitoring_attrs_argparser(parser, hide_help)
    parser.add_argument(
            '--nr_targets', metavar='<number>', nargs='+', type=int,
            help='number of monitoring targets for each context (in order)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--nr_ctxs', metavar='<number>', nargs='+', type=int,
                        help='number of contexts for each kdamond (in order)'
                        if not hide_help else argparse.SUPPRESS)

def set_damos_argparser(parser, hide_help):
    parser.add_argument('--damos_action', metavar='<action>', nargs='+',
                        action='append', default=[],
                        help=' '.join([
                            'damos action to apply to the target regions.',
                            '<action> should be {%s}.' %
                            ','.join(_damon.damos_actions),
                            ])
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--damos_sz_region', metavar=('<min>', '<max>'),
                        nargs=2, default=[], action='append',
                        help='min/max size of damos target regions (bytes)'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_access_rate', metavar=('<min>', '<max>'),
            nargs=2, default=[], action='append',
            help='min/max access rate of damos target regions (percent)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_age', metavar=('<min>', '<max>'), nargs=2,
            default=[], action='append',
            help='min/max age of damos target regions (microseconds)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--damos_apply_interval', metavar='<microseconds>',
                        action='append', default=[],
                        help='the apply interval for the scheme'
                        if not hide_help else argparse.SUPPRESS)
    damos_quotas_help = ' '.join([
        'damos quotas (<time (ms)> [<size (bytes)> [<reset interval (ms)>',
        '[<size priority weight (permil)>',
        '[<access rate priority weight> (permil)',
        '[<age priority weight> (permil)]]]]])'])
    parser.add_argument(
            '--damos_quotas', default=[],
            metavar='<quota parameter>', nargs='+', action='append',
            help=argparse.SUPPRESS)
    parser.add_argument('--damos_quota_interval', default=[],
                        metavar='<milliseconds>', action='append',
                        help='quota reset interval'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--damos_quota_time', default=[],
                        metavar='<milliseconds>', action='append',
                        help='time quota'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--damos_quota_space', default=[], metavar='<bytes>',
                        action='append', help='space quota'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--damos_quota_weights', default=[],
                        metavar='<permil>', nargs=3, action='append',
                        help='quota\'s prioritization weights'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_quota_goal', nargs='+', action='append',
            default=[],
            metavar='<metric or value>',
            help=' '.join([
                'damos quota goal (<metric> <target value> [optional value]).',
                '<metric> should be {%s}.' %
                ','.join(_damon.qgoal_metrics)])
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_nr_quota_goals', type=int, nargs='+',
            default=[], metavar='<integer>',
            help='number of quota goals for each scheme (in order)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_filter', nargs='+', action='append',
            default=[],
            metavar='<<allow|reject> [none] <type> [option]...>',
            help='damos filter' if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_nr_filters', type=int, nargs='+', default=[],
            metavar='<integer>',
            help='number of filters for each scheme (in order)'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--damos_wmarks', nargs=5, action='append', default=[],
            metavar=('<metric (none|free_mem_rate)>', '<interval (us)>',
                '<high mark (permil)>', '<mid mark (permil)>',
                '<low mark (permil)>'),
            help='damos watermarks'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--nr_schemes', metavar='<number>', nargs='+', type=int,
                        help='number of schemes for each context (in order)'
                        if not hide_help else argparse.SUPPRESS)

def set_misc_damon_params_argparser(parser):
    parser.add_argument('-c', '--schemes', metavar='<json string or file>',
	    help='data access monitoring-based operation schemes')
    parser.add_argument('--kdamonds', metavar='<json/yaml string or file>',
            help=' '.join([
                'json or yaml format kdamonds specification to run DAMON for.',
                '\'damo args damon\' can help generating it.']))
    parser.add_argument(
            'deducible_target', type=str, metavar='<deducible string>',
            nargs='?',
            help=' '.join([
                'The implicit monitoring requests.',
                'It could be a command, process id, special keywords, or full',
                'DAMON parameters (same to that for --kdamonds)']))

def set_damon_params_argparser(parser, min_help):
    set_monitoring_argparser(parser, min_help)
    set_damos_argparser(parser, min_help)
    set_misc_damon_params_argparser(parser)
    set_monitoring_attrs_pinpoint_argparser(parser, hide_help=True)

def set_argparser(parser, add_record_options, min_help):
    set_damon_params_argparser(parser, min_help)
    if add_record_options:
        parser.add_argument('-o', '--out', metavar='<file path>', type=str,
                default='damon.data', help='output file path')
    set_common_argparser(parser)
    if min_help:
        if parser.epilog is None:
            parser.epilog = ''
        parser.epilog += ' '.join([
            "DAMON parameters options are also supported.",
            "Do 'damo help damon_param_options -h' for the options."])
