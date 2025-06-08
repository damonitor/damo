# SPDX-License-Identifier: GPL-2.0

"""
Transform DAMON monitoring results record into a heatmap.  The heatmap is
constructed with pixels that each shows when (time), which memory region
(space) was how frequently accessed (heat).  The time and space are represented
by the location of the pixel on the map, while the heat is represented by it's
color.

By default, the output shows the heatmap on the terminal.

If --output raw is given, the output shows the relative time, space, and heat
values of each pixel of the map on each line, like below.

    <time> <space> <heat>
    ...

By constructing the pixels based on the values, the user can draw more
human-readable heatmap.  gnuplot like plot tools can be used.  If '--heatmap'
option is given, this tool does that on behalf of the human when '--heatmap'
option is given.

If --output option is given with a file, the gnuplot-based heatmap image is
generated as the file.
"""

import os
import subprocess
import sys
import tempfile

import _damo_ascii_color
import _damo_fmt_str
import _damo_records
import damo_record_info

class HeatPixel:
    time = None
    addr = None
    heat = None

    def __init__(self, time, addr, heat):
        self.time = time
        self.addr = addr
        self.heat = heat

class HeatMap:
    time_start = None
    time_unit = None
    time_resol = None

    addr_start = None
    addr_unit = None
    addr_resol = None

    pixels = None # list of list of pixels

    def __init__(self, time_start, time_unit, time_resol, addr_start,
                 addr_unit, addr_resol):
        self.time_start = time_start
        self.time_unit = time_unit
        self.time_resol = time_resol

        self.addr_start = addr_start
        self.addr_unit = addr_unit
        self.addr_resol = addr_resol

        self.pixels = []
        for i in range(time_resol):
            self.pixels.append([])
            for j in range(addr_resol):
                pixel_time = time_start + i * time_unit
                pixel_addr = addr_start + j * addr_unit
                self.pixels[-1].append(
                        HeatPixel(int(pixel_time), int(pixel_addr), None))

    def pixels_idx_of_time(self, time_ns):
        return int((time_ns - self.time_start) / self.time_unit)

    def pixel_idx_of_addr(self, addr):
        return int((addr - self.addr_start) / self.addr_unit)

    def add_pixel_heat(self, pixels_idx, pixel_idx, region, snapshot, aggr_ns,
                       df_passed):
        pixel = self.pixels[pixels_idx][pixel_idx]
        observe_start_time = snapshot.start_time
        if aggr_ns is not None:
            observe_start_time -= region.age.aggr_intervals * aggr_ns

        account_time_start = max(observe_start_time, pixel.time)
        account_time_end = min(snapshot.end_time, pixel.time + self.time_unit)
        account_time = account_time_end - account_time_start

        account_addr_start = max(region.start, pixel.addr)
        account_addr_end = min(region.end, pixel.addr + self.addr_unit)
        account_sz = account_addr_end - account_addr_start

        nr_accesses = region.nr_accesses.samples
        if df_passed:
            nr_accesses = nr_accesses * region.sz_filter_passed / region.size()

        heat = nr_accesses * account_time * account_sz

        if pixel.heat is None:
            pixel.heat = 0

        pixel_time_space = self.time_unit * self.addr_unit

        heat += pixel.heat * pixel_time_space
        pixel.heat = float(heat) / pixel_time_space

    def pixels_idxs_range(self, region, snapshot, last_snapshot, aggr_ns):
        start_time = snapshot.start_time
        if aggr_ns is not None:
            start_time -= region.age.aggr_intervals * aggr_ns
        if last_snapshot is not None and start_time < last_snapshot.end_time:
            start_time = last_snapshot.end_time
        return range(
                self.pixels_idx_of_time(start_time),
                self.pixels_idx_of_time(snapshot.end_time) + 1)

    def add_heat(self, snapshot, last_snapshot, aggr_ns, df_passed):
        heatmap_addr_end = self.addr_start + self.addr_unit * self.addr_resol
        for region in snapshot.regions:
            if region.end < self.addr_start or heatmap_addr_end < region.start:
                continue

            for pixels_idx in self.pixels_idxs_range(
                    region, snapshot, last_snapshot, aggr_ns):
                if pixels_idx < 0 or self.time_resol <= pixels_idx:
                    continue
                for pixel_idx in range(
                        self.pixel_idx_of_addr(region.start),
                        self.pixel_idx_of_addr(region.end) + 1):
                    if pixel_idx < 0 or self.addr_resol <= pixel_idx:
                        continue
                    self.add_pixel_heat(
                            pixels_idx, pixel_idx, region, snapshot, aggr_ns,
                            df_passed)

    def highest_lowest_heats(self):
        highest = None
        lowest = None
        for row in self.pixels:
            for pixel in row:
                if pixel.heat is None:
                    continue
                if highest is None or highest < pixel.heat:
                    highest = pixel.heat
                if lowest is None or lowest > pixel.heat:
                    lowest = pixel.heat
        return highest, lowest

    def fmt_gnuplot_str(self, abs_time, abs_addr):
        lines = []
        for row in self.pixels:
            for pixel in row:
                time = pixel.time
                addr = pixel.addr
                if not abs_time:
                    time -= self.time_start
                if not abs_addr:
                    addr -= self.addr_start

                heat = pixel.heat if pixel.heat is not None else 'NaN'
                lines.append('%s\t%s\t%s' % (time, addr, heat))
        return '\n'.join(lines)

    def fmt_ascii_lines_map(self, colorset):
        lines = []
        # add pixels
        highest_heat, lowest_heat = self.highest_lowest_heats()
        if highest_heat is None and lowest_heat is None:
            return
        heat_unit = float(highest_heat + 1 - lowest_heat) / 9
        pixels = self.pixels
        for snapshot in pixels:
            chars = []
            for pixel in snapshot:
                if pixel.heat is None:
                    chars.append('%s ' %
                                 _damo_ascii_color.color_mode_start_txt(
                                     colorset, 4))
                    continue
                heat = int(float(pixel.heat - lowest_heat) / heat_unit)
                heat = min(heat, _damo_ascii_color.max_color_level())
                chars.append('%s%d' %
                        (_damo_ascii_color.color_mode_start_txt(colorset, heat),
                            heat))
            lines.append(''.join(chars) + _damo_ascii_color.color_mode_end_txt())
        return lines

    def fmt_ascii_lines_comments(self, colorset, print_colorset):
        lines = []
        if print_colorset:
            lines.append('# access_frequency: %s' %
                    _damo_ascii_color.color_samples(colorset))

        addr_start = self.addr_start
        addr_len = self.addr_unit * self.addr_resol
        addr_end = addr_start + addr_len
        lines.append('# x-axis: space [%s, %s) (%s)' % (
            _damo_fmt_str.format_sz(addr_start, False),
            _damo_fmt_str.format_sz(addr_end, False),
            _damo_fmt_str.format_sz(addr_len, False)))

        time_start = self.time_start
        time_len = self.time_unit * self.time_resol
        time_end = time_start + time_len
        lines.append('# y-axis: time [%s, %s) (%s)' % (
            _damo_fmt_str.format_time_ns(time_start, False),
            _damo_fmt_str.format_time_ns(time_end, False),
            _damo_fmt_str.format_time_ns(time_len, False)))
        pixels = self.pixels
        lines.append('# resolution: %dx%d (%s and %s for each character)' % (
            len(pixels[1]), len(pixels),
            _damo_fmt_str.format_sz(float(addr_len) / len(pixels[1]), False),
            _damo_fmt_str.format_time_ns(
                float(time_len) / len(pixels), False)))
        return lines

    def fmt_ascii_str(self, colorset, print_colorset):
        lines = self.fmt_ascii_lines_map(colorset)
        lines += self.fmt_ascii_lines_comments(colorset, print_colorset)
        return '\n'.join(lines)

def heatmap_from_records(
        records, time_range, addr_range, resols, df_passed):
    time_start, time_end = time_range
    addr_start, addr_end = addr_range
    time_resol, addr_resol = resols
    time_unit = (time_end - time_start) // time_resol
    addr_unit = (addr_end - addr_start) // addr_resol

    heatmap = HeatMap(time_start, time_unit, time_resol,
                      addr_start, addr_unit, addr_resol)
    last_snapshot = None
    for record in records:
        aggr_ns = None
        if record.intervals is not None:
            aggr_ns = record.intervals.aggr * 1000
        for snapshot in record.snapshots:
            heatmap.add_heat(snapshot, last_snapshot, aggr_ns, df_passed)
            last_snapshot = snapshot
    return heatmap

def mk_heatmap(args, address_range_idx, __records):
    records = []
    for record in __records:
        if record.kdamond_idx != args.kdamond_idx:
            continue
        if record.context_idx != args.context_idx:
            continue
        if record.scheme_idx != args.scheme_idx:
            continue
        if record.target_id != args.tid:
            continue
        records.append(record)

    return heatmap_from_records(
            records, args.time_range, args.address_range[address_range_idx],
            args.resol, args.df_passed)

def fmt_heats(args, address_range_idx, __records):
    heatmap = mk_heatmap(args, address_range_idx, __records)
    if args.output == 'stdout':
        return heatmap.fmt_ascii_str(
                args.stdout_colorset, not args.stdout_skip_colorset_example)

    return heatmap.fmt_gnuplot_str(args.abs_time, args.abs_addr)

def set_missed_args(args, records):
    if (args.kdamond_idx is not None and args.context_idx is not None and
        args.scheme_idx is not None and args.tid is not None and
        args.time_range is not None and args.address_range is not None):
        return
    guides = damo_record_info.get_guide_info(records)
    guide = guides[0]
    if args.kdamond_idx is None:
        args.kdamond_idx = guide.kdamond_idx
    if args.context_idx is None:
        args.context_idx = guide.context_idx
    if args.scheme_idx is None:
        args.scheme_idx = guide.scheme_idx
    if args.tid is None:
        args.tid = guide.tid

    proper_guides = [g for g in guides if
                g.kdamond_idx == args.kdamond_idx and
                g.context_idx == args.context_idx and g.scheme_idx ==
                args.scheme_idx and g.tid == args.tid]
    if len(proper_guides) == 0:
        print('set_missed_args fail due to no proper guide')
        exit(1)
    guide = proper_guides[0]

    if not args.time_range:
        args.time_range = [guide.start_time, guide.end_time]

    if not args.address_range:
        if args.draw_range == 'hottest':
            hottest_contig_region = sorted(
                    guide.contig_regions, key=lambda x: x.heat_per_byte(),
                    reverse=True)[0]
            args.address_range = [[hottest_contig_region.start_addr,
                                  hottest_contig_region.end_addr]]
        elif args.draw_range == 'all':
            args.address_range = [
                    [r.start_addr, r.end_addr] for r in guide.contig_regions]

def plot_range(orig_range, use_absolute_val):
    plot_range = [x for x in orig_range]
    if not use_absolute_val:
        plot_range[0] -= orig_range[0]
        plot_range[1] -= orig_range[0]
    return plot_range

def plot_heatmap(data_file, output_file, args, address_range, range_idx,
                 highest_heat, lowest_heat):
    terminal = output_file.split('.')[-1]
    if not terminal in ['pdf', 'jpeg', 'png', 'svg']:
        os.remove(data_file)
        print("Unsupported plot output type.")
        exit(-1)
    if range_idx > 0:
        tokens = output_file.split('.')
        tokens.insert(-1, '%d' % range_idx)
        output_file = '.'.join(tokens)

    x_range = plot_range(args.time_range, args.abs_time)
    y_range = plot_range(address_range, args.abs_addr)

    gnuplot_cmd = """
    set term %s;
    set output '%s';
    set key off;
    set xrange [%f:%f];
    set yrange [%f:%f];
    set cbrange [%f:%f];
    set xlabel 'Time (ns)';
    set ylabel 'Address (bytes)';
    plot '%s' using 1:2:3 with image;""" % (
            terminal, output_file, x_range[0], x_range[1],
            y_range[0], y_range[1], highest_heat, lowest_heat, data_file)
    try:
        subprocess.call(['gnuplot', '-e', gnuplot_cmd])
    except Exception as e:
        print('executing gnuplot failed (%s)' % e)
    os.remove(data_file)

def main(args):
    records, err = _damo_records.get_records(record_file=args.input)
    if err != None:
        print('monitoring result file (%s) parsing failed (%s)' %
                (args.input, err))
        exit(1)

    # Use 80x40 or 500x500 resolution as default for stdout or image plots
    if args.resol is None:
        if args.output == 'stdout':
            args.resol = [40, 80]
        else:
            args.resol = [500, 500]

    if args.guide:
        damo_record_info.pr_guide(records)
        return
    if args.guide_human is True:
        damo_record_info.pr_guide(records, raw_numbers=False)
        return

    if args.time_range is not None:
        args.time_range = [
                _damo_fmt_str.text_to_ns(x) for x in args.time_range]
    if args.address_range is not None:
        for idx, address_range in enumerate(args.address_range):
            args.address_range[idx] = [
                    _damo_fmt_str.text_to_bytes(x) for x in address_range]

    set_missed_args(args, records)

    heats_list = []
    for idx in range(len(args.address_range)):
        heatmap = mk_heatmap(args, idx, records)

        if args.output == 'stdout':
            print(heatmap.fmt_ascii_str(
                args.stdout_colorset, not args.stdout_skip_colorset_example))
            continue
        else:
            gnuplot_data_str = heatmap.fmt_gnuplot_str(
                    args.abs_time, args.abs_addr)
            if args.output == 'raw':
                print(gnuplot_data_str)
                continue
            # use gnuplot-based image plot
            highest_heat, lowest_heat = heatmap.highest_lowest_heats()
            tmp_path = tempfile.mkstemp()[1]
            with open(tmp_path, 'w') as f:
                f.write(gnuplot_data_str)
            plot_heatmap(
                    tmp_path, args.output, args, args.address_range[idx], idx,
                    highest_heat, lowest_heat)

def set_argparser(parser):
    parser.add_argument('--output', metavar='<output>', default='stdout',
                        help=' '.join(
                            ['output heatmap to generate.',
                             'can be a pdf/png/jpeg/svg file or',
                             'special keywords (\'stdout\', \'raw\')']))
    parser.add_argument('--input', '-i', type=str, metavar='<file>', nargs='+',
            default=['damon.data'], help='input file name')

    parser.add_argument('--kdamond_idx', metavar='<int>', type=int,
                        help='kdamond idx of record to print heatmap for')
    parser.add_argument('--context_idx', metavar='<int>', type=int,
                        help='context idx of record to print heatmap for')
    parser.add_argument('--scheme_idx', metavar='<int>', type=int,
                        help='scheme idx of record to print heatmap for')
    parser.add_argument('--tid', metavar='<id>', type=int,
                        help='target id of record to print heatmap for')
    parser.add_argument('--resol', metavar='<resolution>', type=int, nargs=2,
            help='resolutions for time and address axes')
    parser.add_argument('--time_range', metavar='<time>', nargs=2,
            help='start and end time of the output in nanoseconds')
    parser.add_argument('--draw_range', choices=['hottest', 'all'],
                        default='hottest',
                        help='which ranges to draw heatmap for')
    parser.add_argument('--address_range', metavar='<address>', nargs=2,
                        action='append',
                        help='start and end address of the output')
    parser.add_argument('--abs_time', action='store_true', default=False,
            help='display absolute time in output')
    parser.add_argument('--abs_addr', action='store_true', default=False,
            help='display absolute address in output')

    parser.add_argument('--guide', action='store_true',
            help='print a guidance for the ranges and resolution settings')
    parser.add_argument('--guide_human', action='store_true',
                        help='print the guidance in human-friendly format')
    parser.add_argument('--stdout_colorset', default='gray',
            choices=['gray', 'flame', 'emotion'],
            help='color theme for access frequencies')
    parser.add_argument('--stdout_skip_colorset_example',
            action='store_true',
            help='skip printing example colors at the output')
    parser.add_argument('--df_passed', action='store_true',
                        help='show heatmap for only DAMOS filter-passed parts')
    parser.description = 'Show when which address ranges were how frequently accessed'
