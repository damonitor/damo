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
                        HeatPixel(int(pixel_time), int(pixel_addr), 0.0))

    def pixels_idx_of_time(self, time_ns):
        return int((time_ns - self.time_start) / self.time_unit)

    def pixel_idx_of_addr(self, addr):
        return int((addr - self.addr_start) / self.addr_unit)

    def add_pixel_heat(self, pixels_idx, pixel_idx, region, snapshot):
        pixel = self.pixels[pixels_idx][pixel_idx]
        account_time_start = max(snapshot.start_time, pixel.time)
        account_time_end = min(snapshot.end_time, pixel.time + self.time_unit)
        account_time = account_time_end - account_time_start

        account_addr_start = max(region.start, pixel.addr)
        account_addr_end = min(region.end, pixel.addr + self.addr_unit)
        account_sz = account_addr_end - account_addr_start

        heat = region.nr_accesses.samples * account_time * account_sz

        if pixel.heat is None:
            pixel.heat = 0

        pixel_time_space = self.time_unit * self.addr_unit

        heat += pixel.heat * pixel_time_space
        pixel.heat = float(heat) / pixel_time_space

    def add_heat(self, snapshot):
        for pixels_idx in range(self.pixels_idx_of_time(snapshot.start_time),
                                self.pixels_idx_of_time(snapshot.end_time) + 1):
            if pixels_idx < 0 or self.time_resol <= pixels_idx:
                continue
            for region in snapshot.regions:
                for pixel_idx in range(
                        self.pixel_idx_of_addr(region.start),
                        self.pixel_idx_of_addr(region.end) + 1):
                    if pixel_idx < 0 or self.addr_resol <= pixel_idx:
                        continue
                    self.add_pixel_heat(
                            pixels_idx, pixel_idx, region, snapshot)

def heat_pixels_from_snapshots(snapshots, time_range, addr_range, resols):
    """Get heat pixels for monitoring snapshots."""
    time_resol, addr_resol = resols
    time_start, time_end = time_range
    addr_start, addr_end = addr_range
    time_unit = (time_end - time_start) / float(time_resol)
    space_unit = (addr_end - addr_start) / float(addr_resol)

    pixels = [[HeatPixel(int(time_start + i * time_unit),
                    int(addr_start + j * space_unit), 0.0)
            for j in range(addr_resol)] for i in range(addr_resol)]
    if time_end == time_start:
        return pixels

    heatmap = HeatMap(time_start, time_unit, time_resol, addr_start,
                      space_unit, addr_resol)
    for snapshot in snapshots:
        heatmap.add_heat(snapshot)

    return heatmap.pixels

def fmt_ascii_heatmap(pixels, time_range, addr_range, resols, colorset,
        print_colorset):
    lines = []
    highest_heat = None
    lowest_heat = None
    for snapshot in pixels:
        for pixel in snapshot:
            if pixel.heat is None:
                continue
            if highest_heat == None or highest_heat < pixel.heat:
                highest_heat = pixel.heat
            if lowest_heat == None or lowest_heat > pixel.heat:
                lowest_heat = pixel.heat
    if highest_heat == None and lowest_heat == None:
        return
    heat_unit = float(highest_heat + 1 - lowest_heat) / 9

    for snapshot in pixels:
        chars = []
        for pixel in snapshot:
            if pixel.heat is None:
                chars.append(' ')
                continue
            heat = int(float(pixel.heat - lowest_heat) / heat_unit)
            heat = min(heat, _damo_ascii_color.max_color_level())
            chars.append('%s%d' %
                    (_damo_ascii_color.color_mode_start_txt(colorset, heat),
                        heat))
        lines.append(''.join(chars) + _damo_ascii_color.color_mode_end_txt())
    if print_colorset:
        lines.append('# access_frequency: %s' %
                _damo_ascii_color.color_samples(colorset))
    lines.append('# x-axis: space (%d-%d: %s)' % (addr_range[0], addr_range[1],
        _damo_fmt_str.format_sz(addr_range[1] - addr_range[0], False)))
    lines.append('# y-axis: time (%d-%d: %s)' % (time_range[0], time_range[1],
        _damo_fmt_str.format_time_ns(time_range[1] - time_range[0], False)))
    lines.append('# resolution: %dx%d (%s and %s for each character)' % (
        len(pixels[1]), len(pixels),
        _damo_fmt_str.format_sz(
            float(addr_range[1] - addr_range[0]) / len(pixels[1]), False),
        _damo_fmt_str.format_time_ns(
            float(time_range[1] - time_range[0]) / len(pixels), False)))
    return '\n'.join(lines)

def fmt_heats(args, address_range_idx, __records):
    tid = args.tid
    tres, ares = args.resol
    tmin, tmax = args.time_range
    amin, amax = args.address_range[address_range_idx]

    tunit = (tmax - tmin) // tres
    aunit = (amax - amin) // ares

    # Compensate the values so that those fit with the resolution
    tmax = tmin + tunit * tres
    amax = amin + aunit * ares

    records = []
    for record in __records:
        if record.target_id == tid:
            records.append(record)

    lines = []
    for record in records:
        pixels = heat_pixels_from_snapshots(record.snapshots,
                [tmin, tmax], [amin, amax], [tres, ares])

        if args.output == 'stdout':
            lines.append(fmt_ascii_heatmap(pixels, [tmin, tmax], [amin, amax],
                    [tres, ares], args.stdout_colorset, not
                    args.stdout_skip_colorset_example))
            continue

        highest_heat = None
        for row in pixels:
            for pixel in row:
                if pixel.heat is None:
                    continue
                if highest_heat is None or highest_heat < pixel.heat:
                    highest_heat = pixel.heat
        unknown_heat = highest_heat * -1

        for row in pixels:
            for pixel in row:
                time = pixel.time
                addr = pixel.addr
                if not args.abs_time:
                    time -= tmin
                if not args.abs_addr:
                    addr -= amin

                heat = pixel.heat if pixel.heat is not None else unknown_heat
                lines.append('%s\t%s\t%s' % (time, addr, heat))
    return '\n'.join(lines)

def set_missed_args(args, records):
    if args.tid and args.time_range and args.address_range:
        return
    guides = damo_record_info.get_guide_info(records)
    guide = guides[0]
    if not args.tid:
        args.tid = guide.tid
    for g in guides:
        if g.tid == args.tid:
            guide = g
            break

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

def plot_heatmap(data_file, output_file, args, address_range, range_idx):
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
    set xlabel 'Time (ns)';
    set ylabel 'Address (bytes)';
    plot '%s' using 1:2:3 with image;""" % (terminal, output_file, x_range[0],
            x_range[1], y_range[0], y_range[1], data_file)
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

    set_missed_args(args, records)

    heats_list = []
    for idx in range(len(args.address_range)):
        heats_list.append(fmt_heats(args, idx, records))

    if args.output in ['stdout', 'raw']:
        for heats in heats_list:
            print(heats)
        return

    for idx, address_range in enumerate(args.address_range):
        # use gnuplot-based image plot
        tmp_path = tempfile.mkstemp()[1]
        with open(tmp_path, 'w') as f:
            f.write(heats_list[idx])
        plot_heatmap(tmp_path, args.output, args, address_range, idx)

def set_argparser(parser):
    parser.add_argument('--output', metavar='<output>', default='stdout',
                        help=' '.join(
                            ['output heatmap to generate.',
                             'can be a pdf/png/jpeg/svg file or',
                             'special keywords (\'stdout\', \'raw\')']))
    parser.add_argument('--input', '-i', type=str, metavar='<file>',
            default='damon.data', help='input file name')

    parser.add_argument('--tid', metavar='<id>', type=int,
            help='target id')
    parser.add_argument('--resol', metavar='<resolution>', type=int, nargs=2,
            help='resolutions for time and address axes')
    parser.add_argument('--time_range', metavar='<time>', type=int, nargs=2,
            help='start and end time of the output')
    parser.add_argument('--draw_range', choices=['hottest', 'all'],
                        default='hottest',
                        help='which ranges to draw heatmap for')
    parser.add_argument('--address_range', metavar='<address>', type=int,
                        nargs=2, action='append',
                        help='start and end address of the output')
    parser.add_argument('--abs_time', action='store_true', default=False,
            help='display absolute time in output')
    parser.add_argument('--abs_addr', action='store_true', default=False,
            help='display absolute address in output')

    parser.add_argument('--guide', action='store_true',
            help='print a guidance for the ranges and resolution settings')
    parser.add_argument('--stdout_colorset', default='gray',
            choices=['gray', 'flame', 'emotion'],
            help='color theme for access frequencies')
    parser.add_argument('--stdout_skip_colorset_example',
            action='store_true',
            help='skip printing example colors at the output')
    parser.description = 'Show when which address ranges were how frequently accessed'
