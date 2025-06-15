# SPDX-License-Identifier: GPL-2.0

import argparse
import code
import copy
import json
import math
import os
import signal
import sys
import tempfile
import time

import _damo_ascii_color
import _damo_fmt_str
import _damo_print
import _damo_records
import _damon
import _damon_args

class Formatter:
    keyword = None
    format_fn = None
    help_msg = None

    def __init__(self, keyword, format_fn, help_msg):
            self.keyword = keyword
            self.format_fn = format_fn
            self.help_msg = help_msg

    def __str__(self):
        return '%s\n%s' % (self.keyword, self.help_msg)

record_formatters = [
        Formatter('<kdamond index>',
            lambda record, fmt: '%s' % record.kdamond_idx,
            'index of the record\'s kdamond'),
        Formatter('<context index>',
            lambda record, fmt: '%s' % record.context_idx,
            'index of the record\'s DAMON context'),
        Formatter('<scheme index>',
            lambda record, fmt: '%s' % record.scheme_idx,
            'index of the record\'s DAMOS scheme'),
        Formatter('<target id>',
            lambda record, fmt: '%s' % record.target_id,
            'index of the record\'s DAMON target'),
        Formatter('<abs start time>',
            lambda record, fmt:
            _damo_fmt_str.format_time_ns(record.snapshots[0].start_time,
                                         fmt.raw_number),
            'absolute time of the start of the record'),
        Formatter('<duration>',
            lambda record, fmt:
            _damo_fmt_str.format_time_ns(
                record.snapshots[-1].end_time - record.snapshots[0].start_time,
                fmt.raw_number),
            'duration of the record'),
        Formatter('<intervals>',
                  lambda record, fmt: record_intervals(record, fmt.raw_number),
                  'monitoring intervals'),
        Formatter('<intervals goal>',
                  lambda record, fmt:
                  record.intervals.intervals_goal.to_str(fmt.raw_number),
                  'monitoring intervals'),
        Formatter('<format strings>',
                  lambda record, fmt: format_strings(fmt),
                  'current format strings')
        ]

snapshot_formatters = [
        Formatter('<total bytes>',
            lambda snapshot, record, fmt:
            _damo_fmt_str.format_sz(snapshot.total_bytes, fmt.raw_number),
            'total bytes of regions in the snapshot'),
        Formatter('<duration>',
            lambda snapshot, record, fmt:
                  _damo_fmt_str.format_time_ns(
                      snapshot.end_time - snapshot.start_time, fmt.raw_number),
                  'access monitoring duration for the snapshot'),
        Formatter('<start time>',
            lambda snapshot, record, fmt:
                  _damo_fmt_str.format_time_ns(
                      snapshot.start_time -
                      record.snapshots[0].start_time, fmt.raw_number),
                  'access monitoring start time for the snapshot, ' \
                          'relative to the record start time'),
        Formatter('<end time>',
            lambda snapshot, record, fmt:
                  _damo_fmt_str.format_time_ns(
                      snapshot.end_time - record.snapshots[0].start_time,
                      fmt.raw_number),
                  'access monitoring end time for the snapshot, ' \
                          'relative to the record end time'),
        Formatter('<abs start time>',
            lambda snapshot, record, fmt:
            _damo_fmt_str.format_time_ns(snapshot.start_time, fmt.raw_number),
            'absolute access monitoring start time for the snapshot'),
        Formatter('<abs end time>',
            lambda snapshot, record, fmt:
            _damo_fmt_str.format_time_ns(snapshot.end_time, fmt.raw_number),
            'absolute access monitoring end time for the snapshot'),
        Formatter('<number of regions>',
            lambda snapshot, record, fmt:
            _damo_fmt_str.format_nr(len(snapshot.regions), fmt.raw_number),
            'the number of regions in the snapshot'),
        Formatter('<region box colors>',
            lambda snapshot, record, fmt:
            _damo_ascii_color.color_samples(fmt.region_box_format.colorset),
            'available colors for the region box'),
        Formatter('<region box description>',
            lambda snapshot, record, fmt:
            fmt.region_box_format.description_msg(fmt.raw_number),
            'description about region box (what and how it represents)'),
        Formatter('<temperature-sz histogram>',
                  lambda snapshot, record, fmt:
                  temperature_sz_hist_str(snapshot, record, fmt, False),
                  'temperature to total size of the regions histogram'),
        Formatter('<temperature-df-passed-sz histogram>',
                  lambda snapshot, record, fmt:
                  temperature_sz_hist_str(snapshot, record, fmt, True),
                  ' '.join(['temperature to total size of DAMOS filters (df)',
                            'passed regions histogram'])),
        Formatter('<recency-sz histogram>',
                  lambda snapshot, record, fmt:
                  recency_hist_str(snapshot, record, fmt, False),
                  'idle time to total size of the regions histogram'),
        Formatter('<recency-df-passed-sz histogram>',
                  lambda snapshot, record, fmt:
                  recency_hist_str(snapshot, record, fmt, True),
                  ' '.join(['idle time to total size of',
                            'DAMOS filters (df) passed regions histogram'])),
        Formatter('<recency percentiles>',
                  lambda snapshot, record, fmt:
                  recency_percentiles(snapshot, record, fmt, False),
                  'per-byte idle time distribution in percentiles'),
        Formatter('<df-passed recency percentiles>',
                  lambda snapshot, record, fmt:
                  recency_percentiles(snapshot, record, fmt, True),
                  ' '.join(['per-df-passed byte idle time',
                            'distribution in percentiles'])),
        Formatter('<temperature percentiles>',
                  lambda snapshot, record, fmt:
                  temperature_percentiles(snapshot, record, fmt, False),
                  'per-byte access temperature distribution in percentiles'),
        Formatter('<df-passed temperature percentiles>',
                  lambda snapshot, record, fmt:
                  temperature_percentiles(snapshot, record, fmt, True),
                  ' '.join(['per-df-passed byte access temperature',
                            'distribution in percentiles'])),

        Formatter('<heatmap>',
                  lambda snapshot, record, fmt:
                  heatmap_str(snapshot, record, fmt),
                  'heatmap of the snapshot'),
        Formatter('<filters passed heatmap>',
                  lambda snapshot, record, fmt:
                  df_passed_heatmap_str(snapshot, record, fmt),
                  'heatmap of the snapshot for filter-passed regions'),
        Formatter(
            '<filters passed type>',
            lambda snapshot, record, fmt: filters_pass_type_of(record),
            'type of <filters passed bytes> memory'),
        Formatter(
                '<filters passed bytes>',
                lambda snapshot, record, fmt:
                filters_passed_bytes(snapshot, fmt),
                'bytes of regions that passed DAMOS filters'),
        Formatter(
                '<positive access samples ratio>',
                lambda snapshot, record, fmt:
                positive_access_sample_ratio(snapshot, record, fmt),
                'positive access samples ratio'),
        Formatter(
                '<estimated memory bandwidth>',
                lambda snapshot, record, fmt:
                estimated_mem_bw(snapshot, record, fmt),
                'estimated memory bandwidth'),
        Formatter(
                '<filters passed estimated memory bandwidth>',
                lambda snapshot, record, fmt:
                estimated_mem_bw(snapshot, record, fmt,
                                 filter_passed_only=True),
                'estimated memory bandwidth'),
        Formatter(
                '<intervals tuning status>',
                lambda snapshot, record, fmt:
                intervals_tuning_status(snapshot, record, fmt),
                'intervals tuning status'),
        Formatter(
                '<damos stats>',
                lambda snapshot, record, fmt:
                damos_stats_str(snapshot, record, fmt),
                'DAMOS stats for the snapshot-retrieval scheme'),
        ]

region_formatters = [
        Formatter(
            '<index>',
            lambda index, region, fmt:
            _damo_fmt_str.format_nr(index, fmt.raw_number),
            'index of the region in the regions of the snapshot'),
        Formatter(
            '<start address>',
            lambda index, region, fmt:
            _damo_fmt_str.format_sz(region.start, fmt.raw_number),
            'start address of the region'),
        Formatter(
            '<end address>',
            lambda index, region, fmt:
            _damo_fmt_str.format_sz(region.end, fmt.raw_number),
            'end address of the region'),
        Formatter(
            '<size>',
            lambda index, region, fmt:
            _damo_fmt_str.format_sz(region.size(), fmt.raw_number),
            'size of the region'),
        Formatter(
            '<access rate>',
            lambda index, region, fmt:
            _damo_fmt_str.format_percent(region.nr_accesses.percent,
                                         fmt.raw_number),
            'monitored access rate of the region'),
        Formatter(
            '<age>',
            lambda index, region, fmt:
            _damo_fmt_str.format_time_us(region.age.usec, fmt.raw_number),
            'how long the access pattern of the region has maintained'),
        Formatter(
            '<temperature>',
            lambda index, region, fmt:
            temperature_str(region, fmt.raw_number, fmt),
            'access temperature of the region'),
        Formatter(
            '<filters passed bytes>',
            lambda index, region, fmt:
            _damo_fmt_str.format_sz(region.sz_filter_passed, fmt.raw_number)
            if region.sz_filter_passed is not None else 'N/A',
            'bytes of the region that passed DAMOS filters'),
        Formatter(
            '<box>',
            lambda index, region, fmt:
            fmt.region_box_format.to_str(region),
            'user-customizable (via --region_box_*) box ' \
                    '(age/access_rate/size by default)'),
        ]

def record_intervals(record, raw_number):
    intervals = record.intervals
    return 'sample %s, aggr %s' % (
            _damo_fmt_str.format_time_us(intervals.sample, raw_number),
            _damo_fmt_str.format_time_us(intervals.aggr, raw_number))

def format_strings(fmt):
    return '\n'.join([
        'record head: "%s"' % fmt.format_record_head,
        'snapshot head: "%s"' % fmt.format_snapshot_head,
        'region: "%s"' % fmt.format_region,
        'snapshot tail: "%s"' % fmt.format_snapshot_tail,
        'record tail: "%s"' % fmt.format_record_tail,
        ])

def filters_passed_bytes(snapshot, fmt):
    bytes = 0
    for region in snapshot.regions:
        if region.sz_filter_passed is None:
            return 'N/A'
        bytes += region.sz_filter_passed
    return _damo_fmt_str.format_sz(bytes, fmt.raw_number)

def positive_access_sample_ratio(snapshot, record, fmt):
    max_samples_per_region = record.intervals.aggr / record.intervals.sample
    max_samples = max_samples_per_region * len(snapshot.regions)
    nr_samples = 0
    for region in snapshot.regions:
        region.nr_accesses.add_unset_unit(record.intervals)
        nr_samples += region.nr_accesses.samples
    return _damo_fmt_str.format_percent(
            nr_samples * 100 / max_samples, fmt.raw_number)

def intervals_tuning_status(snapshot, record, fmt):
    max_samples_per_region = record.intervals.aggr / record.intervals.sample
    max_observation = 0
    observation = 0
    for region in snapshot.regions:
        region.nr_accesses.add_unset_unit(record.intervals)
        max_observation += max_samples_per_region * region.size()
        observation += region.size() * region.nr_accesses.samples
    return '%s (%s / %s) %s %s' % (
            _damo_fmt_str.format_percent(
                observation * 100 / max(max_observation, 1), fmt.raw_number),
            _damo_fmt_str.format_sz(observation, fmt.raw_number),
            _damo_fmt_str.format_sz(max_observation, fmt.raw_number),
            _damo_fmt_str.format_time_us(record.intervals.sample,
                                         fmt.raw_number),
            _damo_fmt_str.format_time_us(record.intervals.aggr,
                                         fmt.raw_number),
            )

def damos_stats_str(snapshot, record, fmt):
    if snapshot.damos_stats is None:
        return 'none'
    return snapshot.damos_stats.to_str(fmt.raw_number)

def infer_aggr_time_us(snapshot, record):
    snapshot_aggr_us = (snapshot.end_time - snapshot.start_time) / 1000
    record_aggr_us = record.intervals.aggr
    # if error is small enough, use simpler number
    if abs(snapshot_aggr_us - record_aggr_us) / record_aggr_us < 0.1:
        return record_aggr_us
    return snapshot_aggr_us

def estimated_mem_bw(snapshot, record, fmt, filter_passed_only=False):
    access_bytes = 0
    for region in snapshot.regions:
        if filter_passed_only is True:
            bytes = region.sz_filter_passed
        else:
            bytes = region.size()
        access_bytes += bytes * region.nr_accesses.samples
    aggr_interval_sec = infer_aggr_time_us(snapshot, record) / 1000000
    bw_per_sec = access_bytes / aggr_interval_sec
    return '%s per second' % _damo_fmt_str.format_sz(
            bw_per_sec, fmt.raw_number)

def filters_pass_type_of(record):
    ops_filters = [f for f in record.scheme_filters if f.handled_by_ops()]
    if len(ops_filters) == 0:
        return 'n/a'
    text = ', '.join(['%s' % f for f in ops_filters])
    return text

def get_linearscale_hist_ranges(minv, maxv, nr_ranges, cumulate):
    hist_ranges = []
    total_interval = maxv + 1 - minv
    interval = max(math.ceil(total_interval / nr_ranges), 1)
    for i in range(nr_ranges):
        if cumulate:
            start_range = minv
        else:
            start_range = minv + interval * i
        hist_ranges.append([start_range, minv + interval * (i + 1)])
    return hist_ranges

def get_logscale_hist_ranges(minv, maxv, nr_ranges, cumulate):
    initial_interval = max(int((maxv - minv) / 2**nr_ranges), 1)
    # start from 1 second interval
    ranges = [[minv, minv + initial_interval]]
    while ranges[-1][-1] < maxv:
        last_interval = ranges[-1][1] - ranges[-1][0]
        if cumulate:
            start_range = minv
        else:
            start_range = ranges[-1][-1]
        ranges.append([start_range, ranges[-1][-1] + last_interval * 2])
    return ranges

def get_hist_ranges(minv, maxv, nr_ranges, logscale, cumulate):
    if logscale:
        return get_logscale_hist_ranges(minv, maxv, nr_ranges, cumulate)
    return get_linearscale_hist_ranges(minv, maxv, nr_ranges, cumulate)

def histogram_str(hist):
    """
    Format histogram string to show.
    Args:
        hist (list): List of lines of histogram to show.
    Returns:
        str: A string of the histogram that formatted in a user-friendly way.
    """
    yvals = [entry[2] for entry in hist]
    min_yval = min(yvals)
    max_yval = max(yvals)
    max_xval_range_str = max([len(entry[0]) for entry in hist])
    max_yval_str = max([len(entry[1]) for entry in hist])
    max_dots = 20
    yval_dot_interval = max(int((max_yval - min_yval) / max_dots), 1)
    lines = []
    for xrange_str, y_str, yval in hist:
        xrange_str = '%s%s' % (xrange_str,
                               ' ' * (max_xval_range_str - len(xrange_str)))
        y_str = '%s%s' % (y_str,
                           ' ' * (max_yval_str - len(y_str)))

        nr_dots = min(math.ceil((yval - min_yval) / yval_dot_interval),
                      max_dots)
        bar = '|%s%s|' % ('*' * nr_dots, ' ' * (max_dots - nr_dots))
        lines.append('%s %s %s' % (xrange_str, y_str, bar))
    return '\n'.join(lines)

def get_distribution(snapshot, fmt, get_metric_fn, aggr_us, get_count_fn):
    dist = {}
    for region in snapshot.regions:
        metric_val = get_metric_fn(region, fmt, aggr_us)
        if not metric_val in dist:
            dist[metric_val] = 0
        dist[metric_val] += get_count_fn(region, fmt)
    return dist

def get_sorted_ranged_historgram(
        hist, fmt, fmt_x_fn, parse_x_fn, fmt_y_fn, y_aggr_fn):
    metrics = sorted(hist.keys())
    hist2 = []
    if fmt.hist_ranges is not None:
        hist_ranges = []
        for i in range(0, len(fmt.hist_ranges), 2):
            hist_ranges.append(
                    [parse_x_fn(fmt.hist_ranges[i]),
                     parse_x_fn(fmt.hist_ranges[i + 1])])
    else:
        min_metric, max_metric = metrics[0], metrics[-1]
        hist_ranges = get_hist_ranges(
                min_metric, max_metric, 10, fmt.hist_logscale,
                fmt.hist_cumulate)
    raw = fmt.raw_number
    for min_m, max_m in hist_ranges:
        yval = y_aggr_fn(
                [hist[x] for x in metrics if x >= min_m and x < max_m])
        metric_range_str = '[%s, %s)' % (
                fmt_x_fn(min_m, raw), fmt_x_fn(max_m, raw))
        yval_str = fmt_y_fn(yval, raw)
        hist2.append([metric_range_str, yval_str, yval])
    return hist2

def get_sz_region(region, fmt):
    return region.size()

def get_df_passed_sz_region(region, fmt):
    return region.sz_filter_passed

def sz_hist_str(snapshot, fmt, df_passed_sz, get_metric_fn, aggr_us,
                fmt_metric_fn, parse_metric_fn):
    if len(snapshot.regions) == 0:
        return 'no region in snapshot'
    if df_passed_sz is True:
        get_count_fn = get_df_passed_sz_region
    else:
        get_count_fn = get_sz_region
    dist = get_distribution(
            snapshot, fmt, get_metric_fn, aggr_us, get_count_fn)
    hist = get_sorted_ranged_historgram(
            dist, fmt, fmt_metric_fn, parse_metric_fn, _damo_fmt_str.format_sz,
            lambda sz_list: sum(sz_list))

    return histogram_str(hist)

def get_temperature(region, fmt, aggr_us):
    # set size weight zero
    weights = [0, fmt.temperature_weights[1], fmt.temperature_weights[2]]
    return temperature_of(region, weights)

def temperature_sz_hist_str(snapshot, record, fmt, df_passed_sz):
    return sz_hist_str(
            snapshot, fmt, df_passed_sz, get_temperature,
            infer_aggr_time_us(snapshot, record) , _damo_fmt_str.format_nr,
            _damo_fmt_str.text_to_nr)

def get_idle_time(region, fmt, aggr_interval):
    if region.nr_accesses.percent > 0:
        return 0
    return region.age.usec + aggr_interval

def recency_hist_str(snapshot, record, fmt, df_passed_sz):
    if len(snapshot.regions) == 0:
        return 'no region in snapshot'

    return sz_hist_str(
            snapshot, fmt, df_passed_sz, get_idle_time,
            infer_aggr_time_us(snapshot, record), _damo_fmt_str.format_time_us,
            _damo_fmt_str.text_to_us)

def get_percentiles_to_show(fmt):
    percentiles_range = fmt.percentiles_range
    if percentiles_range is None:
        percentiles_to_show = [0, 1, 25, 50, 75, 99, 100]
    else:
        if len(percentiles_range) <= 3:
            percentiles_to_show = list(range(*percentiles_range))
        else:
            percentiles_to_show = sorted(percentiles_range)
    return percentiles_to_show

def get_percentile_values(snapshot, aggr_us, recency_or_temperature, df_passed,
                          percentiles_to_show, fmt):
    if recency_or_temperature == 'recency':
        get_metric_fn = get_idle_time
    else:
        get_metric_fn = get_temperature
    regions = sorted(snapshot.regions,
                     key=lambda r: get_metric_fn(r, fmt, aggr_us))
    if df_passed is True:
        total_sz = sum(r.sz_filter_passed for r in regions)
    else:
        total_sz = sum(r.size() for r in regions)
    percentile_values = []
    percentile = 0
    for r in regions:
        if df_passed is True:
            percentile += r.sz_filter_passed * 100 / total_sz
        else:
            percentile += r.size() * 100 / total_sz
        while len(percentiles_to_show) > 0:
            if percentile < percentiles_to_show[0]:
                break
            percentile_values.append(
                    [percentiles_to_show[0], get_metric_fn(r, fmt, aggr_us)])
            percentiles_to_show = percentiles_to_show[1:]
        if percentile >= 100.0:
            break
    if 100 in percentiles_to_show:
        percentile_values.append([100, get_metric_fn(r, fmt, aggr_us)])
    return percentile_values

def fmt_percentile_str_head(recency_or_temperature, df_passed, fmt):
    if recency_or_temperature == 'recency':
        if fmt.raw_number:
            legend_str = '<idle time (us)>'
        else:
            legend_str = '<idle time>'
    else:
        legend_str = '<temperature (weights: %s)>' % fmt.temperature_weights
    if df_passed is True:
        return '<df-passed percentile> %s' % legend_str
    else:
        return '<percentile> %s' % legend_str

def fmt_percentile_str(percentile_values, fmt, recency_or_temperature,
                       df_passed):
    lines = [fmt_percentile_str_head(recency_or_temperature, df_passed, fmt)]
    if recency_or_temperature == 'recency':
        fmt_fn = _damo_fmt_str.format_time_us
    else:
        fmt_fn = _damo_fmt_str.format_nr
    percentile_txts = []
    idletime_txts = []
    bars = []
    percentile_txts = ['%d' % p for p, v in percentile_values]
    max_percentile_txt_len = max([len(p) for p in percentile_txts])
    idletime_txts = [fmt_fn(v, fmt.raw_number) for p, v in percentile_values]
    max_idletime_txt_len = max([len(i) for i in idletime_txts])

    min_val = percentile_values[0][-1]
    max_val = percentile_values[-1][-1]
    max_dots = 20
    if max_val != min_val:
        val_per_dot = (max_val - min_val) / max_dots
    else:
        val_per_dot = 1

    for idx, percentile_txt in enumerate(percentile_txts):
        percentile_padding = ' ' * (max_percentile_txt_len -
                                    len(percentile_txt))
        idletime_txt = idletime_txts[idx]
        idletime_padding = ' ' * (max_idletime_txt_len - len(idletime_txt))
        bar_length = int((percentile_values[idx][1] - min_val) / val_per_dot)
        bar = '|%s%s|' % ('*' * bar_length, ' ' * (max_dots - bar_length))
        lines.append('%s%s  %s%s  %s' % (
            percentile_padding, percentile_txt,
            idletime_padding, idletime_txt, bar))
    return '\n'.join(lines)

def percentiles_str(snapshot, record, fmt, df_passed, recency_or_temperature):
    if len(snapshot.regions) == 0:
        return 'no region in snapshot'

    percentiles_to_show = get_percentiles_to_show(fmt)
    percentile_values = get_percentile_values(
            snapshot, infer_aggr_time_us(snapshot, record),
            recency_or_temperature, df_passed, percentiles_to_show, fmt)
    return fmt_percentile_str(percentile_values, fmt, recency_or_temperature,
                              df_passed)

def recency_percentiles(snapshot, record, fmt, df_passed):
    return percentiles_str(snapshot, record, fmt, df_passed, 'recency')

def temperature_percentiles(snapshot, record, fmt, df_passed):
    return percentiles_str(snapshot, record, fmt, df_passed, 'temperature')

def temperature_str(region, raw, fmt):
    temperature = temperature_of(region, fmt.temperature_weights)
    return _damo_fmt_str.format_nr(temperature, raw)

def region_in(start, end, regions):
    for region in regions:
        if region.end <= start:
            continue
        if end <= region.start:
            break
        return True
    return False

def region_after(addr, regions):
    for region in regions:
        if region.start > addr:
            return region
    return None

class HeatPixel:
    start = None
    end = None
    total_heat = None
    temperature = None
    is_void = None

    def __init__(self, start, end, regions, temperature_weights):
        self.start = start
        self.end = end

        self.total_heat = 0
        self.is_void = True
        for region in regions:
            if region.end <= start:
                continue
            if end <= region.start:
                break
            self.is_void = False
            self.add_temperature(region, temperature_weights)
        self.temperature = self.total_heat / (self.end - self.start)

    def add_temperature(self, region, weights):
        start = self.start
        end = self.end
        # caller should ensure region intersects with self
        if start <= region.start and region.end <= end:
            # region is in the pixel
            pass
        elif region.start <= start and end <= region.end:
            # pixel is in the region
            region = copy.deepcopy(region)
            region.start = start
            region.end = end
        elif region.start < start:
            # region intersecting right part
            # <region>
            #    <pixel>
            region = copy.deepcopy(region)
            region.start = start
        else:
            # region intersecting left part
            #    <region>
            # <pixel>
            region = copy.deepcopy(region)
            region.end = end
        self.total_heat += temperature_of(region, weights) * (region.size())

def heatmap_pixels_minmax_temps(snapshot, sz_unit, fmt):
    pixels = []
    min_temperature = None
    max_temperature = None
    start = snapshot.regions[0].start
    while start < snapshot.regions[-1].end:
        end = start + sz_unit
        pixels.append(HeatPixel(
            start, end, snapshot.regions, fmt.temperature_weights))
        if pixels[-1].is_void is True:
            next_region = region_after(end, snapshot.regions)
            if next_region is None:
                break
            start = next_region.start // sz_unit * sz_unit
            pixels[-1].end = start
        else:
            pixel = pixels[-1]
            if min_temperature is None or pixel.temperature < min_temperature:
                min_temperature = pixel.temperature
            if max_temperature is None or pixel.temperature > max_temperature:
                max_temperature = pixel.temperature
            start = end
    return pixels, min_temperature, max_temperature

def heatmap_dots(
        pixels, min_temperature, max_temperature, fmt, sz_unit, static):
    max_color_level = _damo_ascii_color.max_color_level()
    temperature_unit = (max_temperature - min_temperature) / max_color_level
    # single region?
    if temperature_unit == 0:
        temperature_unit = max_temperature / max_color_level
    if temperature_unit == 0:
        temperature_unit = 1
    dots = []
    for pixel in pixels:
        if pixel.is_void is True:
            nr_dots = (pixel.end - pixel.start) / sz_unit
            if not static and nr_dots > 4:
                dots.append('[...]')
            else:
                dots += ['.'] * int(nr_dots)
            continue
        temp_level = int(
                (pixel.temperature - min_temperature) / temperature_unit)
        dots.append(_damo_ascii_color.colored(
            '%d' % temp_level, fmt.snapshot_heatmap_colorset, temp_level))
    return ''.join(dots)

def heatmap_str(snapshot, record, fmt):
    if len(snapshot.regions) == 0:
        return 'n/a (no region)'
    raw = fmt.raw_number
    # whether to display monitoring gaps as size-relative or not
    static = fmt.snapshot_heatmap_static
    if static:
        total_sz = snapshot.regions[-1].end - snapshot.regions[0].start
    else:
        total_sz = 0
        for region in snapshot.regions:
            total_sz += region.size()
    map_length = fmt.snapshot_heatmap_width
    sz_unit = total_sz / map_length

    pixels, min_temperature, max_temperature = heatmap_pixels_minmax_temps(
            snapshot, sz_unit, fmt)
    dots = heatmap_dots(
            pixels, min_temperature, max_temperature, fmt, sz_unit, static)

    comment = '# min/max temperatures: %s, %s, column size: %s' % (
            _damo_fmt_str.format_nr(min_temperature, raw),
            _damo_fmt_str.format_nr(max_temperature, raw),
            _damo_fmt_str.format_sz(sz_unit, raw))
    return '%s\n%s' % (dots, comment)

def df_passed_heatmap_str(snapshot, record, fmt):
    regions = []
    for region in snapshot.regions:
        cp_region = copy.deepcopy(region)
        if region.sz_filter_passed == 0:
            continue
        regions.append(cp_region)
    return heatmap_str(
            _damo_records.DamonSnapshot(
                snapshot.start_time, snapshot.end_time, regions,
                total_bytes=None),
            record, fmt)

def rescale(val, orig_scale_minmax, new_scale_minmax, logscale=True):
    '''Return a value in new scale

    Parameters
    ----------
    val : int, float
        The value to rescale
    orig_scale_minmax : list
        min/max values of original scale
    new_scale_minmax : list
        min/max values of new scale
    logscale : bool
        whether to use logscale (True) or linearscale (False)

    Returns
    -------
    float
        The rescaled value
    '''

    if logscale:
        log_val = math.log(val, 2) if val > 0 else 0
        log_minmax = [math.log(v, 2) if v > 0 else 0
                for v in orig_scale_minmax]
        val = log_val
        orig_scale_minmax = log_minmax
    orig_length = orig_scale_minmax[1] - orig_scale_minmax[0]
    new_length = new_scale_minmax[1] - new_scale_minmax[0]
    ratio = new_length / orig_length if orig_length > 0 else 1
    return (val - orig_scale_minmax[0]) * ratio + new_scale_minmax[0]

class BoxValue:
    val = None
    val_min_max = None      # list of min/max
    display_min_max = None  # list of min/max
    display_logscale = None # bool

    def __init__(self, val, val_min_max, display_min_max, display_logscale):
        self.val = val
        self.val_min_max = val_min_max
        self.display_min_max = display_min_max
        self.display_logscale = display_logscale

    def display_value(self):
        return rescale(self.val, self.val_min_max, self.display_min_max,
                self.display_logscale)

class ColoredBox:
    # BoxValue
    length = None
    color = None
    height = None

    colorset = None
    horizontal_align = None

    def __init__(self, length, horizontal_align, color, colorset, height):
        self.length = length
        self.color = color
        self.horizontal_align = horizontal_align
        self.colorset = colorset
        self.height = height

    def __str__(self):
        length = int(self.length.display_value())

        if self.height.val != None:
            height = int(self.height.display_value())
        else:
            self.height.display_min, self.height.display_max = [1, 1]
            height = 1

        if type(self.color.val) == str:
            row = '%s' % (self.color.val * length)
        else:
            color_level = int(self.color.display_value())
            row = '%s' % _damo_ascii_color.colored(
                    ('%d' % color_level) * length, self.colorset, color_level)
        row = '|%s|' % row

        if self.horizontal_align == 'right':
            indent = ' ' * (self.length.display_min_max[1] - length)
            row = indent + row

        box = '\n'.join([row] * height)
        if self.height.display_min_max[1] > 1:
            box += '\n'
        return box

class SortedAccessPatterns:
    sz_regions = None
    access_rates_percent = None
    ages_us = None

    def __init__(self, records):
        self.sz_regions = []
        self.access_rates_percent = []
        self.ages_us = []

        for record in records:
            for snapshot in record.snapshots:
                for region in snapshot.regions:
                    self.sz_regions.append(region.size())

                    region.nr_accesses.add_unset_unit(record.intervals)
                    self.access_rates_percent.append(
                            region.nr_accesses.percent)

                    region.age.add_unset_unit(record.intervals)
                    self.ages_us.append(region.age.usec)
        self.sz_regions.sort()
        self.access_rates_percent.sort()
        self.ages_us.sort()

class RegionBoxAttr:
    value_name = None
    display_min_max = None
    display_logscale = None

    def __init__(self, value_name, display_min_max, display_logscale):
        self.value_name = value_name
        self.display_min_max = display_min_max
        self.display_logscale = display_logscale

class RegionBoxFormat:
    sorted_access_patterns = None
    length = None
    horizontal_align = None
    color = None
    colorset = None
    height = None

    def __init__(self, sorted_access_patterns, length, horizontal_align, color,
                 colorset, height):
        self.sorted_access_patterns = sorted_access_patterns
        self.length = length
        self.horizontal_align = horizontal_align
        self.color = color
        self.colorset = colorset
        self.height = height

    def minmax(self, value_name):
        if value_name == 'size':
            sorted_vals = self.sorted_access_patterns.sz_regions
        elif value_name == 'access_rate':
            sorted_vals = self.sorted_access_patterns.access_rates_percent
        elif value_name == 'age':
            sorted_vals = self.sorted_access_patterns.ages_us
        return sorted_vals[0], sorted_vals[-1]

    def val_minmax(self, region, value_name):
        minval, maxval = self.minmax(value_name)
        if value_name == 'size':
            return region.size(), [minval, maxval]
        elif value_name == 'access_rate':
            return region.nr_accesses.percent, [minval, maxval]
        elif value_name == 'age':
            return region.age.usec, [minval, maxval]
        return None, None

    def to_str(self, region):
        length_val, length_val_minmax = self.val_minmax(region,
                self.length.value_name)
        color_val, color_val_minmax = self.val_minmax(region,
                self.color.value_name)
        if color_val == None:
            color_val = '-'
        height_val, height_val_minmax = self.val_minmax(region,
                self.height.value_name)

        box = '%s' % ColoredBox(
                BoxValue(length_val, length_val_minmax,
                    self.length.display_min_max, self.length.display_logscale),
                self.horizontal_align,
                BoxValue(color_val, color_val_minmax, [0, 9],
                    self.color.display_logscale),
                self.colorset,
                BoxValue(height_val, height_val_minmax,
                    self.height.display_min_max, self.height.display_logscale))
        return box

    def format_min_max(self, minval, maxval, value_name, raw):
        if value_name == 'size':
            return '[%s, %s]' % (_damo_fmt_str.format_sz(minval, raw),
                    _damo_fmt_str.format_sz(maxval, raw))
        if value_name == 'age':
            return '[%s, %s] ' % (_damo_fmt_str.format_time_us(minval, raw),
                    _damo_fmt_str.format_time_us(maxval, raw))
        if value_name == 'access_rate':
            return '[%s, %s]' % (_damo_fmt_str.format_percent(minval, raw),
                    _damo_fmt_str.format_percent(maxval, raw))

    def description_msg(self, raw):
        lines = []
        minval, maxval = self.minmax(self.length.value_name)
        lines.append('# length: %s (represents %s with [%d, %d] columns in %s)'
                % (self.length.value_name,
                    self.format_min_max(minval, maxval,
                        self.length.value_name, raw),
                    self.length.display_min_max[0],
                    self.length.display_min_max[1],
                    'logscale'
                    if self.length.display_logscale else 'linearscale'))

        minval, maxval = self.minmax(self.color.value_name)
        lines.append('# color: %s (represents %s with [%d, %d] number and ' \
                'color (%s) in %s)'
                % (self.color.value_name,
                    self.format_min_max(minval, maxval,
                        self.color.value_name, raw),
                    self.color.display_min_max[0],
                    self.color.display_min_max[1],
                    _damo_ascii_color.color_samples(self.colorset),
                    'logscale'
                    if self.color.display_logscale else 'linearscale'))

        minval, maxval = self.minmax(self.height.value_name)
        lines.append('# height: %s (represents %s with [%d, %d] rows in %s)'
                % (self.height.value_name,
                    self.format_min_max(minval, maxval,
                        self.height.value_name, raw),
                    self.height.display_min_max[0],
                    self.height.display_min_max[1],
                    'logscale'
                    if self.height.display_logscale else 'linearscale'))
        return '\n'.join(lines)

def apply_min_chars(min_chars, field_name, txt):
    # min_chars: [[<field name>, <number of min chars>]...]
    for name, nr in min_chars:
        try:
            nr = int(nr)
        except:
            print('wrong min_chars: %s' % min_chars)

        if name == field_name:
            if len(txt) >= nr:
                return txt
            txt += ' ' * (nr - len(txt))
            return txt
    return txt

def format_output(template, formatters, fmt, record, snapshot=None,
                  region=None, index=None):
    if template == '':
        return
    for formatter in formatters:
        if template.find(formatter.keyword) == -1:
            continue
        if formatters == record_formatters:
            txt = formatter.format_fn(record, fmt)
        elif formatters == snapshot_formatters:
            txt = formatter.format_fn(snapshot, record, fmt)
        elif formatters == region_formatters:
            txt = formatter.format_fn(index, region, fmt)
        txt = apply_min_chars(fmt.min_chars_for, formatter.keyword, txt)
        template = template.replace(formatter.keyword, txt)
    template = template.replace('\\n', '\n')
    return template


def temperature_of(region, weights):
    sz_weight, access_rate_weight, age_weight = weights
    sz_score = region.size() * sz_weight
    ar_score = region.nr_accesses.percent * access_rate_weight
    age_score = region.age.usec * age_weight
    score = sz_score + ar_score + age_score

    if region.nr_accesses.percent > 0:
        return score
    else:
        return -1 * score

def sorted_regions(regions, sort_fields, sort_dsc_keys, temperature_weights):
    for field in sort_fields:
        dsc = sort_dsc_keys != None and ('all' in sort_dsc_keys or
                                         field in sort_dsc_keys)
        if field == 'address':
            regions = sorted(regions, key=lambda r: r.start, reverse=dsc)
        elif field == 'access_rate':
            regions = sorted(regions, key=lambda r: r.nr_accesses.percent,
                    reverse=dsc)
        elif field == 'age':
            regions = sorted(regions, key=lambda r: r.age.usec, reverse=dsc)
        elif field == 'size':
            regions = sorted(regions, key=lambda r: r.size(), reverse=dsc)
        elif field == 'temperature':
            regions = sorted(
                    regions, reverse=dsc,
                    key=lambda r: temperature_of(r, temperature_weights))
    return regions

def fmt_records(fmt, records):
    sorted_access_patterns = SortedAccessPatterns(records)
    fmt.region_box_format = RegionBoxFormat(sorted_access_patterns,
            RegionBoxAttr(fmt.region_box_values[0],
                fmt.region_box_min_max_length,
                fmt.region_box_scales[0] == 'log'), fmt.region_box_align,
            RegionBoxAttr(fmt.region_box_values[1],
                [0, 9], fmt.region_box_scales[1] == 'log'),
            fmt.region_box_colorset,
            RegionBoxAttr(fmt.region_box_values[2],
                fmt.region_box_min_max_height,
                fmt.region_box_scales[2] == 'log'))

    outputs = []
    for record in records:
        outputs.append(
                format_output(
                    fmt.format_record_head, record_formatters, fmt, record))
        snapshots = record.snapshots

        for sidx, snapshot in enumerate(snapshots):
            outputs.append(
                    format_output(
                        fmt.format_snapshot_head, snapshot_formatters,
                        fmt, record, snapshot))
            for r in snapshot.regions:
                r.nr_accesses.add_unset_unit(record.intervals)
                r.age.add_unset_unit(record.intervals)
            for idx, r in enumerate(
                    sorted_regions(snapshot.regions, fmt.sort_regions_by,
                        fmt.sort_regions_dsc, fmt.temperature_weights)):
                outputs.append(
                        format_output(
                            fmt.format_region, region_formatters,
                            fmt, record, snapshot, r, idx))
            outputs.append(
                    format_output(
                        fmt.format_snapshot_tail, snapshot_formatters,
                        fmt, record, snapshot))

            if sidx < len(snapshots) - 1 and not fmt.total_sz_only():
                outputs.append('')
        outputs.append(
                format_output(
                    fmt.format_record_tail, record_formatters, fmt, record))
    outputs = [o for o in outputs if o is not None]
    return '\n'.join(outputs)

def pr_records_raw_form(records, raw_number):
    lines = []
    for record in records:
        snapshots = record.snapshots
        if len(snapshots) == 0:
            continue

        base_time = snapshots[0].start_time
        lines.append('base_time_absolute: %s\n' %
                _damo_fmt_str.format_time_ns(base_time, raw_number))

        for snapshot in snapshots:
            lines.append('monitoring_start:    %16s' %
                    _damo_fmt_str.format_time_ns(
                        snapshot.start_time - base_time, raw_number))
            lines.append('monitoring_end:      %16s' %
                    _damo_fmt_str.format_time_ns(
                        snapshot.end_time - base_time, raw_number))
            lines.append('monitoring_duration: %16s' %
                    _damo_fmt_str.format_time_ns(
                        snapshot.end_time - snapshot.start_time,
                        raw_number))
            lines.append('target_id: %s' % record.target_id)
            lines.append('nr_regions: %s' % len(snapshot.regions))
            lines.append('# %10s %12s  %12s  %11s %5s' %
                    ('start_addr', 'end_addr', 'length', 'nr_accesses', 'age'))
            for r in snapshot.regions:
                lines.append("%012x-%012x (%12s) %11d %5d" %
                        (r.start, r.end,
                            _damo_fmt_str.format_sz(r.size(), raw_number),
                            r.nr_accesses.samples, r.age.aggr_intervals
                                if r.age.aggr_intervals != None else -1))
            lines.append('')
    lines.append('')
    _damo_print.pr_with_pager_if_needed('\n'.join(lines))

def pr_records(fmt, records, dont_use_pager):
    if fmt.json:
        _damo_print.pr_with_pager_if_needed(
                json.dumps([r.to_kvpairs(fmt.raw_number) for r in records],
                           indent=4))
    elif fmt.raw:
        pr_records_raw_form(records, fmt.raw_number)
    else:
        to_show = fmt_records(fmt, records)
        if dont_use_pager:
            print(to_show)
        else:
            _damo_print.pr_with_pager_if_needed(fmt_records(fmt, records))

class ReportFormat:
    sort_regions_by = None
    sort_regions_dsc = None
    temperature_weights = None
    dont_merge_regions = None

    hist_logscale = None
    hist_cumulate = None
    hist_ranges = None

    format_record_head = None
    format_record_tail = None
    format_snapshot_head = None
    format_snapshot_tail = None
    format_region = None

    snapshot_heatmap_width = None
    snapshot_heatmap_colorset = None
    snapshot_heatmap_static = None

    region_box_values = None
    region_box_min_max_height = None
    region_box_min_max_length = None
    region_box_colorset = None
    region_box_scales = None
    region_box_align = None

    # RegionBoxFormat.  Set on fmt_records()
    region_box_format = None

    min_chars_for = None
    raw_number = None
    json = None
    raw = None


    @classmethod
    def from_args(cls, args):
        self = cls()
        self.sort_regions_by = args.sort_regions_by
        self.sort_regions_dsc = args.sort_regions_dsc
        self.temperature_weights = args.temperature_weights
        self.dont_merge_regions = args.dont_merge_regions
        self.hist_logscale = args.hist_logscale
        self.hist_cumulate = args.hist_cumulate
        self.hist_ranges = args.hist_ranges
        self.percentiles_range = args.percentiles_range
        self.format_record_head = args.format_record_head
        self.format_record_tail = args.format_record_tail
        self.format_snapshot_head = args.format_snapshot_head
        self.format_snapshot_tail = args.format_snapshot_tail
        self.format_region = args.format_region
        self.snapshot_heatmap_width = args.snapshot_heatmap_width
        self.snapshot_heatmap_static = args.snapshot_heatmap_static
        self.snapshot_heatmap_colorset = args.snapshot_heatmap_colorset
        self.region_box_values = [
                v if v != 'none' else None for v in args.region_box_values]
        self.region_box_min_max_height = args.region_box_min_max_height
        self.region_box_min_max_length = args.region_box_min_max_length
        self.region_box_colorset = args.region_box_colorset
        self.region_box_scales = args.region_box_scales
        self.region_box_align = args.region_box_align
        self.min_chars_for = args.min_chars_for
        self.raw_number = args.raw_number
        self.json = args.json
        self.raw = args.raw_form
        return self

    def total_sz_only(self):
        return (
                self.format_snapshot_head == '' and
                self.format_region == '' and
                self.format_snapshot_tail == '<total bytes>')

    def to_kvpairs(self, raw):
        return {
                'sort_regions_by': self.sort_regions_by,
                'sort_regions_dsc': self.sort_regions_dsc,
                'temperature_weights': self.temperature_weights,
                'dont_merge_regions': self.dont_merge_regions,
                'hist_logscale': self.hist_logscale,
                'hist_cumulate': self.hist_cumulate,
                'hist_ranges': self.hist_ranges,
                'percentiles_range': self.percentiles_range,
                'format_record_head': self.format_record_head,
                'format_record_tail': self.format_record_tail,
                'format_snapshot_head': self.format_snapshot_head,
                'format_snapshot_tail': self.format_snapshot_tail,
                'format_region': self.format_region,
                'snapshot_heatmap_width': self.snapshot_heatmap_width,
                'snapshot_heatmap_static': self.snapshot_heatmap_static,
                'snapshot_heatmap_colorset': self.snapshot_heatmap_colorset,
                'region_box_values': self.region_box_values,
                'region_box_min_max_height': self.region_box_min_max_height,
                'region_box_min_max_length': self.region_box_min_max_length,
                'region_box_colorset': self.region_box_colorset,
                'region_box_scales': self.region_box_scales,
                'region_box_align': self.region_box_align,
                'min_chars_for': self.min_chars_for,
                'raw_number': self.raw_number,
                'json': self.json,
                }

    @classmethod
    def from_kvpairs(cls, kvpairs):
        self = cls()
        self.sort_regions_by = kvpairs['sort_regions_by']
        self.sort_regions_dsc = kvpairs['sort_regions_dsc']
        self.temperature_weights = kvpairs['temperature_weights']
        self.dont_merge_regions = kvpairs['dont_merge_regions']
        # hist_logscale introduced after v2.7.0
        if 'hist_logscale' in kvpairs:
            self.hist_logscale = kvpairs['hist_logscale']
        else:
            self.hist_logscale = False
        # hist_cumulate introduced after v2.7.6
        if 'hist_cumulate' in kvpairs:
            self.hist_cumulate = kvpairs['hist_cumulate']
        else:
            self.hist_cumulate = False
        # hist_ranges introduced after v2.7.5
        if 'hist_ranges' in kvpairs:
            self.hist_ranges = kvpairs['hist_ranges']
        else:
            self.hist_ranges = None
        # percentiles_range introduced after v2.8.0
        if 'percentiles_range' in kvpairs:
            self.percentiles_range = kvpairs['percentiles_range']
        self.format_record_head = kvpairs['format_record_head']
        self.format_record_tail = kvpairs['format_record_tail']
        self.format_snapshot_head = kvpairs['format_snapshot_head']
        self.format_snapshot_tail = kvpairs['format_snapshot_tail']
        self.format_region = kvpairs['format_region']
        # snapshot_heatmap_width introduced from v2.5.6
        if 'snapshot_heatmap_width' in kvpairs:
            self.snapshot_heatmap_width = kvpairs['snapshot_heatmap_width']
        else:
            self.snapshot_heatmap_width = 80
        # snapshot_heatmap_colorset introduced from v2.5.6
        if 'snapshot_heatmap_colorset' in kvpairs:
            self.snapshot_heatmap_width = kvpairs['snapshot_heatmap_width']
        else:
            self.snapshot_heatmap_width = 'gray'
        # snapshot_heatmap_static introduced after v2.6.7
        if 'snapshot_heatmap_static' in kvpairs:
            self.snapshot_heatmap_static = kvpairs['snapshot_heatmap_static']
        else:
            self.snapshot_heatmap_static = False
        self.region_box_values = kvpairs['region_box_values']
        self.region_box_min_max_height = kvpairs['region_box_min_max_height']
        self.region_box_min_max_length = kvpairs['region_box_min_max_length']
        self.region_box_colorset = kvpairs['region_box_colorset']
        self.region_box_scales = kvpairs['region_box_scales']
        self.region_box_align = kvpairs['region_box_align']
        self.min_chars_for = kvpairs['min_chars_for']
        self.raw_number = kvpairs['raw_number']
        self.json = kvpairs['json']
        return self

def has_ops_filters(records):
    for record in records:
        for scheme_filter in record.scheme_filters:
            if scheme_filter.handled_by_ops():
                return True
    return False

def set_formats_hist_style(args, fmt, records):
    if args.style == 'temperature-sz-hist':
        legend = '<temperature>'
        hist_keyword = '<temperature-sz histogram>'
        filter_passed_hist_keyword = '<temperature-df-passed-sz histogram>'
    else:
        # args.style == 'recency-sz-hist':
        legend = '<idle time (us)>'
        hist_keyword = '<recency-sz histogram>'
        filter_passed_hist_keyword = '<recency-df-passed-sz histogram>'

    snapshot_head_content = []
    if has_ops_filters(records):
        snapshot_head_content += [
                '# damos filters (df): <filters passed type>',
                '%s <df-passed size>' % legend, filter_passed_hist_keyword, '']
    snapshot_head_content += ['%s <total size>' % legend, hist_keyword]
    fmt.format_snapshot_head = '\n'.join(snapshot_head_content)
    fmt.format_region = ''

def has_multiple_snapshots(records):
    for record in records:
        if len(record.snapshots) > 1:
            return True
    return False

def set_formats_percentiles(args, fmt, records, recency_or_temperature):
    snapshot_head_content = []
    if has_multiple_snapshots(records):
        snapshot_head_content.append(
                'snapshot time: [<start time>, <end time>] (<duration>)')
    if has_ops_filters(records):
        snapshot_head_content += [
                '# damos filters (df): <filters passed type>',
                '# df-passed %s percentiles' % recency_or_temperature]
        if recency_or_temperature == 'recency':
            snapshot_head_content.append('<df-passed recency percentiles>')
        else:
            snapshot_head_content.append('<df-passed temperature percentiles>')
        snapshot_head_content.append('')
    if recency_or_temperature == 'recency':
        snapshot_head_content += [
                '# total recency percentiles',
                '<recency percentiles>',
                ]
    else:
        snapshot_head_content += [
                '# total temperature percentiles',
                '<temperature percentiles>',
                ]
    fmt.format_snapshot_head = '\n'.join(snapshot_head_content)
    fmt.format_region = ''

def set_formats_handle_format_set_arg(fmt, format_arg):
    '''Handle --format inputs except 'append' ones'''
    if format_arg is None:
        return
    if len(format_arg) == 1 and len(format_arg[0]) == 1:
        fmt_string = format_arg[0][0]
        if os.path.isfile(fmt_string):
            with open(fmt_string, 'r') as f:
                fmt_string = f.read()
        try:
            return ReportFormat.from_kvpairs(json.loads(fmt_string)), None
        except:
            return None, 'wrong --format option'
    for format_fields in format_arg:
        if len(format_fields) != 3:
            return None, 'wrong --format option (%s)' % format_fields
        action, target_area, fmt_string = format_fields
        if not action in ['set', 'append']:
            return None, 'wrong --format action (%s)' % format_fields
        if not target_area in ['record_head', 'snapshot_head', 'region',
                               'snapshot_tail', 'record_tail']:
            return None, 'wrong --format target area (%s)' % format_fields
        if action == 'set':
            if target_area == 'record_head':
                fmt.format_record_head = fmt_string
            elif target_area == 'snapshot_head':
                fmt.format_snapshot_head = fmt_string
            elif target_area == 'region':
                fmt.format_region = fmt_string
            elif target_area == 'snapshot_tail':
                fmt.format_snapshot_tail = fmt_string
            elif target_area == 'record_tail':
                fmt.format_record_tail = fmt_string

def set_formats_handle_styles(fmt, args, records):
    if args.style is None:
        return

    if args.style == 'simple-boxes':
        fmt.format_snapshot_head = \
                'snapshot time: [<start time>, <end time>] (<duration>)'
        fmt.format_region = \
                '<box> size <size> access rate <access rate> age <age>'
        fmt.region_box_min_max_height = [1, 1]
        fmt.region_box_min_max_length = [1, 40]
        fmt.region_box_align = 'right'
        fmt.region_box_colorset = 'emotion'
    elif args.style in ['temperature-sz-hist', 'recency-sz-hist']:
        set_formats_hist_style(args, fmt, records)
    elif args.style == 'recency-percentiles':
        set_formats_percentiles(args, fmt, records, 'recency')
    elif args.style == 'temperature-percentiles':
        set_formats_percentiles(args, fmt, records, 'temperature')
    elif args.style == 'cold':
        fmt.format_region = '<box> <size> access <access rate> <age>'
        fmt.region_box_min_max_height = [1, 1]
        fmt.region_box_min_max_length = [1, 40]
        fmt.region_box_align = 'right'
        fmt.region_box_colorset = 'emotion'
        fmt.sort_regions_by = ['temperature']
    elif args.style == 'hot':
        fmt.format_region = '<box> <size> access <access rate> <age>'
        fmt.region_box_min_max_height = [1, 1]
        fmt.region_box_min_max_length = [1, 40]
        fmt.region_box_align = 'right'
        fmt.region_box_colorset = 'emotion'
        fmt.sort_regions_by = ['temperature']
        fmt.sort_regions_dsc = ['temperature']

def intervals_goal_enabled(records):
    for record in records:
        if record.intervals is None:
            continue
        if record.intervals.intervals_goal.enabled():
            return True
    return False

def set_formats_record_default(fmt, records):
    if fmt.format_record_head == None:
        if len(records) > 1:
            fmt.format_record_head = \
                    'kdamond <kdamond index> / context <context index>' \
                    ' / scheme <scheme index> / target id <target id> ' \
                    '/ recorded for <duration> from <abs start time>'
        else:
            fmt.format_record_head = ''
    if fmt.format_record_tail is None:
        tail_lines = ['monitoring intervals: <intervals>']
        if intervals_goal_enabled(records):
            tail_lines.append('# <intervals goal>')
        fmt.format_record_tail = '\n'.join(tail_lines)

def set_formats_snapshot_default(fmt, records, args, ops_filters_installed):
    # handle snapshot head and tail
    if fmt.format_snapshot_head == None:
        need_snapshot_head = False
        for record in records:
            if len(record.snapshots) > 1:
                need_snapshot_head = True
                break
        if need_snapshot_head:
            fmt.format_snapshot_head = \
                    'snapshot time: [<start time>, <end time>] ' \
                    '(<duration>)\n<heatmap>'
        else:
            fmt.format_snapshot_head = 'heatmap: <heatmap>'
    if ops_filters_installed:
        fmt.format_snapshot_head += \
                '\n# damos filters (df): <filters passed type>'
        fmt.format_snapshot_head += '\ndf-pass: <filters passed heatmap>'

    if args.region_box:
        if fmt.format_snapshot_tail.find('<region box description>') == -1:
            fmt.format_snapshot_tail = ('%s\n<region box description>' %
                    fmt.format_record_tail)

    if fmt.format_snapshot_tail is None:
        fmt.format_snapshot_tail = \
                'memory bw estimate: <estimated memory bandwidth>\n' \
                'total size: <total bytes>'
        if ops_filters_installed:
            fmt.format_snapshot_tail = \
                    'memory bw estimate: <estimated memory bandwidth>  ' \
                    'df-passed: <filters passed estimated memory bandwidth>' \
                    '\ntotal size: <total bytes>  ' \
                    'df-passed <filters passed bytes>'
        # further check if scheme action is not stat
        if args.tried_regions_of is not None:
            fmt.format_snapshot_tail += '\nscheme stats\n<damos stats>'

def set_formats_region_default(fmt, records, args):
    default_region_format = \
            '<index> addr <start address> size <size> access <access rate> ' \
            'age <age>'
    if args.region_box:
        if fmt.region_box_min_max_height[1] > 1:
            fmt.format_region = '<box>%s' % default_region_format
        else:
            fmt.format_region = '<box>\n%s' % default_region_format

    if fmt.format_region is None:
        fmt.format_region = default_region_format
        for record in records:
            if len(record.scheme_filters) > 0:
                fmt.format_region += ' df-passed <filters passed bytes>'
                break

def set_formats_update_default_formats(fmt, records, args):
    ops_filters_installed = False
    for record in records:
        if len(record.scheme_filters) > 0:
            ops_filters_installed = True
            break

    set_formats_record_default(fmt, records)
    set_formats_snapshot_default(fmt, records, args, ops_filters_installed)
    set_formats_region_default(fmt, records, args)

def set_formats_handle_format_append_arg(fmt, format_args):
    if format_args is None:
        return
    for action, target_area, fmt_string in format_args:
        if action != 'append':
            continue
        if target_area == 'record_head':
            fmt.format_record_head += fmt_string
        elif target_area == 'snapshot_head':
            fmt.format_snapshot_head += fmt_string
        elif target_area == 'region':
            fmt.format_region += fmt_string
        elif target_area == 'snapshot_tail':
            fmt.format_snapshot_tail += fmt_string
        elif target_area == 'record_tail':
            fmt.format_record_tail += fmt_string

def set_formats(args, records):
    fmt = ReportFormat.from_args(args)

    set_formats_handle_format_set_arg(fmt, args.format)
    set_formats_handle_styles(fmt, args, records)

    if args.total_sz_only:
        fmt.format_snapshot_head = ''
        fmt.format_region = ''
        fmt.format_snapshot_tail = '<total bytes>'

    set_formats_update_default_formats(fmt, records, args)
    set_formats_handle_format_append_arg(fmt, args.format)
    return fmt, None

def handle_ls_keywords(args):
    if args.ls_record_format_keywords:
        print("use 'damo help access_format_options record_format_keywords' " \
                "instead")
        return True
    if args.ls_snapshot_format_keywords:
        print("use 'damo help access_format_options " \
                "snapshot_format_keywords' instead")
        return True
    if args.ls_region_format_keywords:
        print("use 'damo help access_format_options " \
                "region_format_keywords' instead")
        return True
    return False

class CacheSpec:
    size = None
    ways = None
    sz_line = None
    nr_cache_sets = None

    def __init__(self, size, ways, sz_line):
        self.size = size
        self.ways = ways
        self.sz_line = sz_line

        self.nr_cache_sets = self.size / self.ways / self.sz_line

    def set_for_pa(self, addr):
        return addr / self.sz_line % self.nr_cache_sets

def translate_regions_to_cache_space(regions, cache_spec):
    set_regions = []
    for i in range(int(cache_spec.nr_cache_sets)):
        set_regions.append(_damon.DamonRegion(
            start=i, end=i+1,
            nr_accesses=0, nr_accesses_unit=_damon.unit_samples,
            age=0, age_unit=_damon.unit_aggr_intervals))
    for region in regions:
        for addr in range(region.start, region.end, cache_spec.sz_line):
            csidx = int(cache_spec.set_for_pa(addr))
            if csidx >= len(set_regions):
                print(csidx, len(set_regions))
                exit(0)
            set_regions[csidx].nr_accesses.samples += \
                    region.nr_accesses.samples
    converted = []
    for set_region in set_regions:
        if len(converted) == 0:
            converted.append(set_region)
            continue
        if converted[-1].nr_accesses.samples == set_region.nr_accesses.samples:
            converted[-1].end = set_region.end
        else:
            converted.append(set_region)
    return converted

def translate_records_to_cache_space(records, cs, cw, cl):
    cache_spec = CacheSpec(cs, cw, cl)
    for record in records:
        for snapshot in record.snapshots:
            snapshot.regions = translate_regions_to_cache_space(
                    snapshot.regions, cache_spec)

signal_received = False

def sighandler(signum, frame):
    global signal_received
    print('\nsignal %s received' % signum)
    signal_received = True

def recursive_del(dirpath):
    for filename in os.listdir(dirpath):
        filepath = os.path.join(dirpath, filename)
        if os.path.isdir(filepath):
            recursive_del(filepath)
        else:
            os.remove(filepath)
    os.rmdir(dirpath)

def handle_exec(cmd, records):
    if cmd == 'interpreter':
        code.interact(
                local=locals(),
                banner="DAMON records are available as 'records'",
                exitmsg='Exit the session.')
        return None
    cmd_fields = cmd.split()
    if not os.path.isfile(cmd_fields[0]):
        return 'first token is not file'
    script_dir_path = tempfile.mkdtemp(prefix='damo_script_')
    script_module_name = 'damo_report_access_script'
    script_file_name = '%s.py' % script_module_name
    with open(cmd_fields[0], 'r') as f:
        with open(os.path.join(script_dir_path, script_file_name), 'w') as f2:
            f2.write(f.read())
    sys.path.append(script_dir_path)
    import damo_report_access_script
    damo_report_access_script.main(records, cmd_fields)
    recursive_del(script_dir_path)
    return None

def read_and_show(args):
    record_filter, err = _damo_records.args_to_filter(args)
    if err != None:
        print(err)
        exit(1)

    if args.input_file == None:
        _damon.ensure_root_and_initialized(args)
        if _damon.any_kdamond_running() is False:
            if os.path.exists('damon.data'):
                args.input_file = 'damon.data'

    dfilters, err = _damon_args.damos_options_to_filters(
            args.snapshot_damos_filter)
    if err is not None:
        print('wrong --snapshot_damos_filter (%s)' % err)
        exit(1)

    if args.repeat is None:
        repeat_delay = 0
        repeat_count = 1
    elif len(args.repeat) == 0:
        repeat_delay = 1
        repeat_count = -1
    elif len(args.repeat) == 2:
        repeat_delay = _damo_fmt_str.text_to_sec(args.repeat[0])
        repeat_count = _damo_fmt_str.text_to_nr(args.repeat[1])
    else:
        print('--repeat receives only zero or two arguments')
        exit(1)

    signal.signal(signal.SIGINT, sighandler)
    global signal_received

    read_show_count = 0
    while read_show_count < repeat_count or repeat_count == -1:
        if signal_received is True:
            break
        records, err = _damo_records.get_records(
                    tried_regions_of=args.tried_regions_of,
                    record_file=args.input_file,
                    snapshot_damos_filters=dfilters,
                    record_filter=record_filter,
                    total_sz_only=args.total_sz_only,
                    dont_merge_regions=args.dont_merge_regions)
        if err != None:
            print(err)
            exit(1)
        if signal_received is True:
            break

        if args.exec:
            err = handle_exec(args.exec, records)
            if err is not None:
                print('format_script handling fail (%s)' % err)
                exit(1)
            time.sleep(repeat_delay)
            read_show_count += 1
            continue

        if len([r for r in records if r.intervals is None]) != 0:
            if not args.json and not args.raw_form:
                print('some records lack the intervals information')
                exit(1)

        fmt, err = set_formats(args, records)
        if err is not None:
            print('format setting failed (%s)' % err)

        if args.on_cache is not None:
            sz_cache = _damo_fmt_str.text_to_bytes(args.on_cache[0])
            ways_cache = _damo_fmt_str.text_to_nr(args.on_cache[1])
            sz_cache_line = _damo_fmt_str.text_to_bytes(args.on_cache[2])
            translate_records_to_cache_space(
                    records, sz_cache, ways_cache, sz_cache_line)

        try:
            pr_records(fmt, records,
                       dont_use_pager = args.repeat is not None)
        except BrokenPipeError as e:
            # maybe user piped to 'less' like pager, and quit from it
            pass

        time.sleep(repeat_delay)
        read_show_count += 1

def main(args):
    handled = handle_ls_keywords(args)
    if handled:
        return

    read_and_show(args)

def add_fmt_args(parser, hide_help=False):
    # how to show, in simple selection
    parser.add_argument(
            '--style', choices=['detailed', 'simple-boxes',
                                'temperature-sz-hist', 'recency-sz-hist',
                                'recency-percentiles',
                                'temperature-percentiles',
                                'cold', 'hot'],
            default='detailed',
            help='output format selection among pre-configures ones')
    # how to show, in highly tunable way
    parser.add_argument(
            '--percentiles_range', nargs='+', type=int, metavar='<number>',
            help='Percentiles to show.  If <=3 arguments are given, '
            'ranges are made with Python range() function. '
            'If >3 argumenta are given, show percentiles of each argument.')
    parser.add_argument(
            '--sort_regions_by', nargs='+',
            choices=['address', 'access_rate', 'age', 'size', 'temperature'],
            default=['address'],
            help='fields to sort regions by'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--sort_regions_dsc',
            choices=['address', 'access_rate', 'age', 'size', 'temperature',
                     'all'],
            nargs='+',
            help='sort regions in descending order for the given keys'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--temperature_weights', type=int, metavar='<int>', nargs=3,
            default=[0, 100, 100],
            help=' '.join(
                ['temperature weights for size, access rate, and age',
                 'of each region']) if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--hist_logscale', action='store_true',
                        help='draw histograms in logscale'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--hist_ranges', nargs='+',
                        help='histogram range values'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--hist_cumulate', action='store_true',
                        help='draw histogram in cumulative way')

    fmt_flexible_metavar='<set|append> ' \
            '<record_head|snapshot_head|region|snapshot_tail|record_tail> ' \
            '<format string>'

    # This option also receives json string or file.  But, no real use case is
    # found.  Keep supporting for now, but hide from the help message.
    parser.add_argument('--format', metavar=fmt_flexible_metavar,
                        action='append', nargs='+',
                        help='visualization format in json format')

    # don't set default for record head and snapshot head because it depends on
    # given number of record and snapshots.  Decide those in set_formats().
    # below five options can be replaced with --format.  Keep backward
    # compatibility support, but hide from help messages.
    parser.add_argument(
            '--format_record_head', metavar='<template>',
            # help='output format to show at the beginning of each record'
            help=argparse.SUPPRESS)
    parser.add_argument('--format_record_tail', metavar='<template>',
                        # help='output format to show at the end of each record'
                        help=argparse.SUPPRESS)
    parser.add_argument(
            '--format_snapshot_head', metavar='<template>',
            # help='output format to show at the beginning of each snapshot'
            help=argparse.SUPPRESS)
    parser.add_argument(
            '--format_snapshot_tail', metavar='<template>',
            # help='output format to show at the end of each snapshot'
            help=argparse.SUPPRESS)
    parser.add_argument('--format_region', metavar='<template>',
                        # help='output format to show for each memory region'
                        help=argparse.SUPPRESS)

    # for snapshot heatmap
    parser.add_argument(
            '--snapshot_heatmap_width', metavar='<number>', default=80,
            type=int,
            help='width of snapshot heatmap'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--snapshot_heatmap_colorset', default='gray',
            choices=_damo_ascii_color.colorsets.keys(),
            help='snapshot heatmap colorset'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--snapshot_heatmap_static', action='store_true',
            help='draw snapshot heatmap as static'
            if not hide_help else argparse.SUPPRESS)

    # for region box
    parser.add_argument('--region_box', action='store_true',
            help='show region access pattern as a box'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_values',
            choices=['size', 'access_rate', 'age', 'none'], nargs=3,
            default=['age', 'access_rate', 'size'],
            help='values to show via the <box>\'s length, color, and height'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_min_max_length', nargs=2, type=int,
            metavar=('<min>', '<max>'), default=[1, 30],
            help='minimum and maximum number of the region box\' length'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_min_max_height', nargs=2, type=int,
            metavar=('<min>', '<max>'), default=[1, 5],
            help='minimum and maximum number of region box\' height'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_colorset', default='gray',
            choices=['gray', 'flame', 'emotion'],
            help='colorset to use for region box'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_scales', choices=['linear', 'log'],
            nargs=3, default=['log', 'linear', 'log'],
            help='scale of region box\' length, color, and height'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--region_box_align', choices=['left', 'right'], default='left',
            help='where to align the region box'
            if not hide_help else argparse.SUPPRESS)

    # misc control
    parser.add_argument(
            '--min_chars_for', nargs=2,
            metavar=('<keyword>', '<number>'), action='append',
            default=[['<index>', 3],
                     ['<start address>', 12],['<end address>', 11],
                     ['<size>', 11], ['<access rate>', 5],
                     ['<age>', 13],
                     ['<filters passed type>', 10],
                     ],
            help='minimum character for each keyword of the format'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--total_sz_only', action='store_true',
            help='print only total size of the regions for each snapshot')
    parser.add_argument('--dont_merge_regions', action='store_true',
            help='don\'t merge contiguous regions of same access pattern'
            if not hide_help else argparse.SUPPRESS)

    parser.add_argument('--raw_number', action='store_true',
            help='use machine-friendly raw numbers')
    parser.add_argument('--json', action='store_true',
            help='print in json format')
    parser.add_argument('--raw_form', action='store_true',
                        help='print in raw format'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--ls_record_format_keywords', action='store_true',
                        # help='list available record format keywords'
                        help=argparse.SUPPRESS)
    parser.add_argument('--ls_snapshot_format_keywords', action='store_true',
                        # help='list available snapshot format keywords'
                        help=argparse.SUPPRESS)
    parser.add_argument('--ls_region_format_keywords', action='store_true',
                        # help='list available region format keywords'
                        help=argparse.SUPPRESS)
    if hide_help:
        if parser.epilog is None:
            parser.epilog = ''
        else:
            parser.epilog += ' '
        parser.epilog += ' '.join([
            "More options for customized format are available.",
            "Do 'damo help access_format_options -h' for those options.",
            ])

def set_argparser(parser):
    parser.description = 'Show DAMON-monitored access pattern'
    parser.epilog=' '.join([
        'If --input_file is not provided, capture snapshot.',
        'If --input_file is not provided, DAMON is not running,',
        'and "damon.data" file exists, use "damon.data" as --input_file.'])

    _damon_args.set_common_argparser(parser)

    # what to show
    _damo_records.set_filter_argparser(parser, hide_help=True)

    parser.add_argument('--input_file', metavar='<file>', nargs='+',
            help='source of the access pattern to show')
    parser.add_argument('--tried_regions_of', nargs=3, type=int,
            action='append',
            metavar=('<kdamond idx>', '<context idx>', '<scheme idx>'),
            help='show tried regions of given schemes')
    _damo_records.set_snapshot_damos_filters_option(parser)
    add_fmt_args(parser, hide_help=True)

    parser.add_argument('--exec', metavar='<command or \'interpreter\'>',
                        help='execute python code with the records')
    parser.add_argument(
            '--on_cache', nargs=3,
            metavar=('<cache size>', '<cache ways>', '<cache line size>'),
            # visualize access patterns on a virtual cache (EXPERIMENTAL)
            help=argparse.SUPPRESS)
    parser.add_argument(
            '--repeat', nargs='*', metavar=('<delay>', '<count>'),
            help='repeat <count> times with <delay> time interval')
