# SPDX-License-Identifier: GPL-2.0

import os

import _damon

def main(args):
    _damon.ensure_root_permission()

    module_name = args.module_name
    param_dir = '/sys/module/damon_%s/parameters' % module_name
    if args.action == 'read':
        if args.parameter is not None:
            with open(os.path.join(param_dir, args.parameter), 'r') as f:
                print(f.read().strip())
        else:
            for param in os.listdir(param_dir):
                with open(os.path.join(param_dir, param), 'r') as f:
                    print('%s: %s' % (param, f.read().strip()))
    elif args.action == 'write':
        if len(args.parameter_value) % 2 != 0:
            print('wrong paramter_value')
            exit(1)

        for i in range(0, len(args.parameter_value), 2):
            param_name = args.parameter_value[i]
            param_val = args.parameter_value[i + 1]
            with open(os.path.join(param_dir, param_name), 'w') as f:
                f.write(param_val)

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='action', dest='action', metavar='<action>')
    subparsers.required = True

    parser_read = subparsers.add_parser('read', help='read parameters')
    parser_read.add_argument(
            'parameter', metavar='<parameter name>', nargs='?',
            help='parameter to read.')

    parser_write = subparsers.add_parser('write', help='write parameters')
    parser_write.add_argument(
            'parameter_value', metavar=('<parameter name> <value>'), nargs='+',
            help='name of the parameter and the value to write')
    return parser
