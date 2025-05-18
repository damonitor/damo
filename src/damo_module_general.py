# SPDX-License-Identifier: GPL-2.0

import os

import _damon

def main(args):
    _damon.ensure_root_permission()

    module_name = args.module_name
    parm_dir = '/sys/module/damon_%s/parameters' % module_name
    if args.action == 'read':
        with open(os.path.join(parm_dir, args.parameter), 'r') as f:
            print(f.read().strip())
    elif args.action == 'write':
        parm_name, parm_val = args.parameter_value
        with open(os.path.join(parm_dir, parm_name), 'w') as f:
            f.write(parm_val)

def set_argparser(parser):
    subparsers = parser.add_subparsers(
            title='action', dest='action', metavar='<action>')
    subparsers.required = True

    parser_read = subparsers.add_parser('read', help='read parameters')
    parser_read.add_argument(
            'parameter', metavar='<parameter name>',
            help='parameter to read.')

    parser_write = subparsers.add_parser('write', help='write parameters')
    parser_write.add_argument(
            'parameter_value', metavar=('<parameter name> <value>'), nargs=2,
            help='name of the parameter and the value to write')
    return parser
