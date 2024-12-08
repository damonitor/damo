# SPDX-License-Identifier: GPL-2.0

import argparse
import copy
import json
import math
import os

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
            lambda record, raw: '%s' % record.kdamond_idx,
            'index of the record\'s kdamond'),
        Formatter('<context index>',
            lambda record, raw: '%s' % record.context_idx,
            'index of the record\'s DAMON context'),
        Formatter('<scheme index>',
            lambda record, raw: '%s' % record.scheme_idx,
            'index of the record\'s DAMOS scheme'),
        Formatter('<target id>',
            lambda record, raw: '%s' % record.target_id,
            'index of the record\'s DAMON target'),
        Formatter('<abs start time>',
            lambda record, raw:
            _damo_fmt_str.format_time_ns(record.snapshots[0].start_time, raw),
            'absolute time of the start of the record'),
        Formatter('<duration>',
            lambda record, raw:
            _damo_fmt_str.format_time_ns(
                record.snapshots[-1].end_time - record.snapshots[0].start_time,
                raw),
            'duration of the record'),
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
            'access monitoring start time for the snapshot, relative to the record start time'),
        Formatter('<end time>',
            lambda snapshot, record, fmt:
                  _damo_fmt_str.format_time_ns(
                      snapshot.end_time - record.snapshots[0].start_time,
                      fmt.raw_number),
            'access monitoring end time for the snapshot, relative to the record end time'),
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
                  temperature_sz_hist_str(snapshot, record, fmt),
                  'temperature to total size of the regions histogram'),
        Formatter('<recency-sz histogram>',
                  lambda snapshot, record, fmt:
                  recency_hist_str(snapshot, record, fmt),
                  'last accessed time to total size of the regions histogram'),
        Formatter('<heatmap>',
                  lambda snapshot, record, fmt:
                  heatmap_str(snapshot, record, fmt),
                  'heatmap of the snapshot'),
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
            '<box>',
            lambda index, region, fmt:
            fmt.region_box_format.to_str(region),
            'user-customizable (via --region_box_*) box (age/access_rate/size by default)'),
        ]

default_record_head_format = 'kdamond <kdamond index> / context <context index> / scheme <scheme index> / target id <target id> / recorded for <duration> from <abs start time>'
default_snapshot_head_format = 'monitored time: [<start time>, <end time>] (<duration>)\n<heatmap>'
default_snapshot_head_format_without_heatmap = 'monitored time: [<start time>, <end time>] (<duration>)'
default_region_format = '<index> addr <start address> size <size> access <access rate> age <age>'

def temperature_sz_hist_str(snapshot, record, fmt):
    raw = fmt.raw_number
    if len(snapshot.regions) == 0:
        return 'no region in snapshot'
    hist = {}
    # set size weight zero
    weights = [0, fmt.temperature_weights[1], fmt.temperature_weights[2]]
    for region in snapshot.regions:
        temperature = temperature_of(region, fmt.temperature_weights)
        if not temperature in hist:
            hist[temperature] = 0
        hist[temperature] += region.size()

    temperatures = sorted(hist.keys())
    min_temp, max_temp = temperatures[0], temperatures[-1]
    interval = max(int((max_temp - min_temp) / 10), 1)
    max_temp = interval * math.ceil(max_temp / interval) + 1

    hist2 = []
    min_sz = None
    max_sz = None
    max_trange_str = None
    max_sz_str = None
    for t in range(min_temp, max_temp, interval):
        min_t = t
        max_t = t + interval
        sz = sum([hist[x] for x in temperatures if x >= min_t and x < max_t])
        if min_sz is None or sz < min_sz:
            min_sz = sz
        if max_sz is None or max_sz < sz:
            max_sz = sz
        trange_str = '[%s, %s)' % (_damo_fmt_str.format_nr(min_t, raw),
                                   _damo_fmt_str.format_nr(max_t, raw))
        if max_trange_str is None or max_trange_str < len(trange_str):
            max_trange_str = len(trange_str)
        sz_str = _damo_fmt_str.format_sz(sz, raw)
        if max_sz_str is None or max_sz_str < len(sz_str):
            max_sz_str = len(sz_str)
        hist2.append([trange_str, sz_str, sz])
    max_dots = 20
    sz_interval = max(int((max_sz - min_sz) / max_dots), 1)
    lines = []
    for trange_str, sz_str, sz in hist2:
        trange_str = '%s%s' % (trange_str,
                               ' ' * (max_trange_str - len(trange_str)))
        sz_str = '%s%s' % (sz_str,
                           ' ' * (max_sz_str - len(sz_str)))

        nr_dots = min(math.ceil((sz - min_sz) / sz_interval), max_dots)
        bar = '|%s%s|' % ('*' * nr_dots, ' ' * (max_dots - nr_dots))
        lines.append('%s %s %s' % (trange_str, sz_str, bar))
    return '\n'.join(lines)

def recency_hist_str(snapshot, record, fmt):
    raw = fmt.raw_number
    if len(snapshot.regions) == 0:
        return 'no region in snapshot'
    hist = {}
    for region in snapshot.regions:
        last_used = -1 * region.age.usec
        if region.nr_accesses.percent > 0:
            last_used = 0
        if not last_used in hist:
            hist[last_used] = 0
        hist[last_used] += region.size()

    last_used_times = sorted(hist.keys())
    min_lut, max_lut = last_used_times[0], last_used_times[-1]
    interval = max(int((max_lut - min_lut) / 10), 1)
    max_lut = interval * math.ceil(max_lut / interval) + 1

    hist2 = []
    min_sz = None
    max_sz = None
    max_trange_str = None
    max_sz_str = None
    for t in range(min_lut, max_lut, interval):
        min_t = t
        max_t = t + interval
        sz = sum([hist[x] for x in last_used_times if x >= min_t and x < max_t])
        if min_sz is None or sz < min_sz:
            min_sz = sz
        if max_sz is None or max_sz < sz:
            max_sz = sz
        trange_str = '[-%s, -%s)' % (
                _damo_fmt_str.format_time_us(-1 * min_t, raw),
                _damo_fmt_str.format_time_us(-1 * max_t, raw))
        if max_trange_str is None or max_trange_str < len(trange_str):
            max_trange_str = len(trange_str)
        sz_str = _damo_fmt_str.format_sz(sz, raw)
        if max_sz_str is None or max_sz_str < len(sz_str):
            max_sz_str = len(sz_str)
        hist2.append([trange_str, sz_str, sz])
    max_dots = 20
    sz_interval = max(int((max_sz - min_sz) / max_dots), 1)
    lines = []
    for trange_str, sz_str, sz in hist2:
        trange_str = '%s%s' % (trange_str,
                               ' ' * (max_trange_str - len(trange_str)))
        sz_str = '%s%s' % (sz_str,
                           ' ' * (max_sz_str - len(sz_str)))

        nr_dots = min(math.ceil((sz - min_sz) / sz_interval), max_dots)
        bar = '|%s%s|' % ('*' * nr_dots, ' ' * (max_dots - nr_dots))
        lines.append('%s %s %s' % (trange_str, sz_str, bar))
    return '\n'.join(lines)

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

def heatmap_str(snapshot, record, fmt):
    raw = fmt.raw_number
    total_sz = 0
    for region in snapshot.regions:
        total_sz += region.size()
    map_length = fmt.snapshot_heatmap_width
    sz_unit = total_sz / map_length

    start = snapshot.regions[0].start
    pixels = []
    min_temperature = None
    max_temperature = None
    while start < snapshot.regions[-1].end:
        end = start + sz_unit
        pixels.append(HeatPixel(
            start, end, snapshot.regions, fmt.temperature_weights))
        if pixels[-1].is_void is True:
            next_region = region_after(end, snapshot.regions)
            if next_region is None:
                break
            start = next_region.start
        else:
            pixel = pixels[-1]
            if min_temperature is None or pixel.temperature < min_temperature:
                min_temperature = pixel.temperature
            if max_temperature is None or pixel.temperature > max_temperature:
                max_temperature = pixel.temperature
            start = end

    max_color_level = _damo_ascii_color.max_color_level()
    temperature_unit = (max_temperature - min_temperature) / max_color_level
    # single region?
    if temperature_unit == 0:
        temperature_unit = max_temperature / max_color_level
    dots = []
    for pixel in pixels:
        if pixel.is_void is True:
            dots.append('[...]')
            continue
        temp_level = int(
                (pixel.temperature - min_temperature) / temperature_unit)
        dots.append(_damo_ascii_color.colored(
            '%d' % temp_level, fmt.snapshot_heatmap_colorset, temp_level))
    dots = ''.join(dots)
    comment = '# min/max temperatures: %s, %s, column size: %s' % (
            _damo_fmt_str.format_nr(min_temperature, raw),
            _damo_fmt_str.format_nr(max_temperature, raw),
            _damo_fmt_str.format_sz(sz_unit, raw))
    return '%s\n%s' % (dots, comment)

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
        lines.append('# color: %s (represents %s with [%d, %d] number and color (%s) in %s)'
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
            txt = formatter.format_fn(record, fmt.raw_number)
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

def pr_records(fmt, records):
    if fmt.json:
        _damo_print.pr_with_pager_if_needed(
                json.dumps([r.to_kvpairs(fmt.raw_number) for r in records],
                           indent=4))
    elif fmt.raw:
        pr_records_raw_form(records, fmt.raw_number)
    else:
        _damo_print.pr_with_pager_if_needed(fmt_records(fmt, records))

class RecordsVisualizationFormat:
    sort_regions_by = None
    sort_regions_dsc = None
    temperature_weights = None
    dont_merge_regions = None

    format_record_head = None
    format_record_tail = None
    format_snapshot_head = None
    format_snapshot_tail = None
    format_region = None

    snapshot_heatmap_width = None
    snapshot_heatmap_colorset = None

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
        self.format_record_head = args.format_record_head
        self.format_record_tail = args.format_record_tail
        self.format_snapshot_head = args.format_snapshot_head
        self.format_snapshot_tail = args.format_snapshot_tail
        self.format_region = args.format_region
        self.snapshot_heatmap_width = args.snapshot_heatmap_width
        self.snapshot_heatmap_colorset = args.snapshot_heatmap_colorset
        self.region_box_values = args.region_box_values
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
                'format_record_head': self.format_record_head,
                'format_record_tail': self.format_record_tail,
                'format_snapshot_head': self.format_snapshot_head,
                'format_snapshot_tail': self.format_snapshot_tail,
                'format_region': self.format_region,
                'snapshot_heatmap_width': self.snapshot_heatmap_width,
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

    def runtime_update(self, records):
        if self.format_record_head == None:
            if len(records) > 1:
                self.format_record_head = default_record_head_format
            else:
                self.format_record_head = ''

        if self.format_snapshot_head == None:
            need_snapshot_head = False
            for record in records:
                if len(record.snapshots) > 1:
                    need_snapshot_head = True
                    break
            if need_snapshot_head:
                self.format_snapshot_head = default_snapshot_head_format
            else:
                self.format_snapshot_head = 'heatmap: <heatmap>'


def set_formats(args):
    if args.style == 'simple-boxes':
        args.format_snapshot_head = default_snapshot_head_format_without_heatmap
        args.format_region = '<box> size <size> access rate <access rate> age <age>'
        args.region_box_min_max_height = [1, 1]
        args.region_box_min_max_length = [1, 40]
        args.region_box_align = 'right'
        args.region_box_colorset = 'emotion'
    elif args.style == 'temperature-sz-hist':
        args.format_snapshot_head = '\n'.join([
            '<temperature> <total size>',
            '<temperature-sz histogram>'])
        args.format_region = ''
    elif args.style == 'recency-sz-hist':
        args.format_snapshot_head = '\n'.join([
            '<last accessed time (us)> <total size>',
            '<recency-sz histogram>'])
        args.format_region = ''

    args.region_box_values = [v if v != 'none' else None
            for v in args.region_box_values]

    if args.total_sz_only:
        args.format_snapshot_head = ''
        args.format_region = ''
        args.format_snapshot_tail = '<total bytes>'

    if args.region_box:
        if args.region_box_min_max_height[1] > 1:
            args.format_region = '<box>%s' % default_region_format
        else:
            args.format_region = '<box>\n%s' % default_region_format
        if args.format_snapshot_tail.find('<region box description>') == -1:
            args.format_snapshot_tail = ('%s\n<region box description>' %
                    args.format_record_tail)

    return RecordsVisualizationFormat.from_args(args)

def handle_ls_keywords(args):
    if args.ls_record_format_keywords:
        print('\n\n'.join(['%s' % f for f in record_formatters]))
        return True
    if args.ls_snapshot_format_keywords:
        print('\n\n'.join(['%s' % f for f in snapshot_formatters]))
        return True
    if args.ls_region_format_keywords:
        print('\n\n'.join(['%s' % f for f in region_formatters]))
        return True
    return False

def main(args):
    handled = handle_ls_keywords(args)
    if handled:
        return

    record_filter, err = _damo_records.args_to_filter(args)
    if err != None:
        print(err)
        exit(1)

    if args.input_file == None:
        _damon.ensure_root_and_initialized(args)
        if _damon.any_kdamond_running() is False:
            if os.path.exists('damon.data'):
                args.input_file = 'damon.data'

    records, err = _damo_records.get_records(
                tried_regions_of=args.tried_regions_of,
                record_file=args.input_file, record_filter=record_filter,
                total_sz_only=args.total_sz_only,
                dont_merge_regions=args.dont_merge_regions)
    if err != None:
        print(err)
        exit(1)

    if len([r for r in records if r.intervals is None]) != 0:
        if not args.json and not args.raw_form:
            print('some records lack the intervals information')
            exit(1)

    if args.format is not None:
        fmt_string = args.format
        if os.path.isfile(fmt_string):
            with open(fmt_string, 'r') as f:
                fmt_string = f.read()
        fmt = RecordsVisualizationFormat.from_kvpairs(json.loads(fmt_string))
    else:
        fmt = set_formats(args)
    fmt.runtime_update(records)
    for record in records:
        try:
            pr_records(fmt, records)
        except BrokenPipeError as e:
            # maybe user piped to 'less' like pager, and quit from it
            pass

def add_fmt_args(parser, hide_help=False):
    # how to show, in simple selection
    parser.add_argument(
            '--style', choices=['detailed', 'simple-boxes',
                                'temperature-sz-hist', 'recency-sz-hist'],
            default='detailed',
            help='output format selection among pre-configures ones')
    # how to show, in highly tunable way
    parser.add_argument(
            '--sort_regions_by', nargs='+',
            choices=['address', 'access_rate', 'age', 'size', 'temperature'],
            default=['address'],
            help='fields to sort regions by')
    parser.add_argument('--sort_regions_dsc',
            choices=['address', 'access_rate', 'age', 'size', 'temperature',
                     'all'],
            nargs='+',
            help='sort regions in descending order for the given keys')
    parser.add_argument(
            '--temperature_weights', type=int, metavar='<int>', nargs=3,
            default=[0, 100, 100],
            help=' '.join(
                ['temperature weights for size, access rate, and age',
                 'of each region']))
    parser.add_argument('--dont_merge_regions', action='store_true',
            help='don\'t merge contiguous regions of same access pattern')

    # don't set default for record head and snapshot head because it depends on
    # given number of record and snapshots.  Decide those in set_formats().
    parser.add_argument(
            '--format_record_head', metavar='<template>',
            help='output format to show at the beginning of each record'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--format_record_tail', metavar='<template>',
                        default='',
                        help='output format to show at the end of each record'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--format_snapshot_head', metavar='<template>',
            help='output format to show at the beginning of each snapshot'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--format_snapshot_tail', metavar='<template>',
            default='total size: <total bytes>',
            help='output format to show at the end of each snapshot'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument(
            '--snapshot_heatmap_width', default=80, type=int,
            help='width of snapshot heatmap')
    parser.add_argument(
            '--snapshot_heatmap_colorset', default='gray',
            choices=_damo_ascii_color.colorsets.keys(),
            help='snapshot heatmap colorset')
    parser.add_argument('--format_region', metavar='<template>',
                        default=default_region_format,
                        help='output format to show for each memory region'
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
    parser.add_argument(
            '--min_chars_for', nargs=2,
            metavar=('<keyword>', '<number>'), action='append',
            default=[['<index>', 3],
                ['<start address>', 12],['<end address>', 11],
                ['<size>', 11], ['<access rate>', 5]],
            help='minimum character for each keyword of the format'
            if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--region_box', action='store_true',
            help='show region access pattern as a box')
    parser.add_argument('--total_sz_only', action='store_true',
            help='print only total size of the regions for each snapshot')
    parser.add_argument('--raw_number', action='store_true',
            help='use machine-friendly raw numbers')
    parser.add_argument('--json', action='store_true',
            help='print in json format')
    parser.add_argument('--raw_form', action='store_true',
                        help='print in raw format')
    parser.add_argument('--ls_record_format_keywords', action='store_true',
                        help='list available record format keywords'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--ls_snapshot_format_keywords', action='store_true',
                        help='list available snapshot format keywords'
                        if not hide_help else argparse.SUPPRESS)
    parser.add_argument('--ls_region_format_keywords', action='store_true',
                        help='list available region format keywords'
                        if not hide_help else argparse.SUPPRESS)
    if hide_help:
        if parser.epilog is None:
            parser.epilog = ''
        else:
            parser.epilog += ' '
        parser.epilog += ' '.join([
            "Accesses format options from 'damo args accesses_format' are",
            "also supported. Do 'damo args accesses_format -h' for the",
            "options.",
            ])

def set_argparser(parser):
    parser.description = 'Show DAMON-monitored access pattern'
    parser.epilog=' '.join([
        'If --input_file is not provided, capture snapshot.',
        'If --input_file is not provided, DAMON is not running,',
        'and "damon.data" file exists, use "damon.data" as --input_file.'])

    _damon_args.set_common_argparser(parser)

    # what to show
    _damo_records.set_filter_argparser(parser)

    parser.add_argument('--input_file', metavar='<file>',
            help='source of the access pattern to show')
    parser.add_argument('--tried_regions_of', nargs=3, type=int,
            action='append',
            metavar=('<kdamond idx>', '<context idx>', '<scheme idx>'),
            help='show tried regions of given schemes')
    add_fmt_args(parser, hide_help=True)
    parser.add_argument('--format', metavar='<json string>',
                        help='visualization format in json format')
