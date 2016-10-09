# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import csv
import json
import sys
import yaml

from gossip.common import pretty_print_dict

from journal import transaction

from sawtooth.client import SawtoothClient

from sawtooth.exceptions import MessageException

from sawtooth.cli.exceptions import CliException


def add_transaction_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('transaction')

    grand_parsers = parser.add_subparsers(title='grandchildcommands',
                                          dest='subcommand')

    epilog = '''
    details:
      list the transaction IDs from the newest to the oldest.
    '''

    list_parser = grand_parsers.add_parser('list', epilog=epilog)
    list_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')
    list_parser.add_argument(
        '--blockcount',
        type=int,
        default=10,
        help='list the maximum number of transaction IDs. Default: 10')
    list_parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='list all of transaction IDs')

    epilog = '''
    details:
      show the contents of transaction or the value associated with key
      within the transaction.
    '''
    show_parser = grand_parsers.add_parser('show', epilog=epilog)
    show_parser.add_argument(
        'transactionID',
        type=str,
        help='the id of the transaction')
    show_parser.add_argument(
        '-k', '--key',
        type=str,
        help='the key within the transaction')
    show_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')
    list_parser.add_argument(
        '--format',
        action='store',
        default='default',
        help='the format of the output. Options: csv, json or yaml.')

    epilog = '''
    details:
      show the status of a specific transaction id.
    '''
    status_parser = grand_parsers.add_parser('status', epilog=epilog)
    status_parser.add_argument(
        'transactionID',
        type=str,
        help='the id of the transaction')
    status_parser.add_argument(
        '--url',
        type=str,
        help='the URL to the validator')


def do_transaction(args):
    subcommands = ['list', 'show', 'status']

    if args.subcommand not in subcommands:
        print 'Unknown sub-command, expecting one of {0}'.format(
            subcommands)
        return

    if args.url is not None:
        url = args.url
    else:
        url = 'http://localhost:8800'

    web_client = SawtoothClient(url)

    try:
        if args.subcommand == 'list':
            if args.all:
                tsctids = web_client.get_transaction_list()
            else:
                tsctids = \
                    web_client.get_transaction_list(
                        block_count=args.blockcount)

            print_trans_info(args, web_client, tsctids)

        elif args.subcommand == 'show':
            tsct_info = \
                web_client.get_transaction(
                    transaction_id=args.transactionID,
                    field=args.key)
            print pretty_print_dict(tsct_info)
            return
        elif args.subcommand == 'status':
            tsct_status = web_client.get_transaction_status(args.transactionID)
            if tsct_status == transaction.Status.committed:
                print 'transaction committed'
            elif tsct_status == transaction.Status.pending:
                print 'transaction still uncommitted'
            elif tsct_status == transaction.Status.unknown:
                print 'unknown transaction'
            elif tsct_status == transaction.Status.failed:
                print 'transaction failed to validate.'
            else:
                print 'transaction returned unexpected status code {0}'\
                    .format(tsct_status)
            return

    except MessageException as e:
        raise CliException(e)


def print_trans_info(args, web_client, tsctids):
    request_field = ['TRANS', 'BLOCK', "STATUS", "TXNTYPE"]
    info_fields_mapping = {request_field[0]: 'Identifier',
                           request_field[1]: 'InBlock',
                           request_field[2]: 'Status',
                           request_field[3]: 'TransactionType'}
    format_mapping = {request_field[0]: '20',
                      request_field[1]: '20',
                      request_field[2]: '8',
                      request_field[3]: '30'}

#     request_field = ['TRANS', 'BLOCK', "STATUS", "TXNTYPE", "NODENAME"]
#     info_fields_mapping = {request_field[0]: 'Identifier',
#                            request_field[1]: 'InBlock',
#                            request_field[2]: 'Status',
#                            request_field[3]: 'TransactionType',
#                            request_field[4]: 'Update.Name'}
#     format_mapping = {request_field[0]: '20',
#                       request_field[1]: '20',
#                       request_field[2]: '8',
#                       request_field[3]: '30',
#                       request_field[4]: '20'}

    if args.format == 'default':
        string_format = ''
        for _, item in enumerate(request_field):
            string_format = string_format +\
                ('{:' + format_mapping[item] + '}').format(item)
        print string_format

        for txn_id in tsctids:
            string_format = ''
            trans_dict = get_trans_info(web_client, txn_id,
                                        info_fields_mapping)
            for _, item in enumerate(request_field):
                string_format = string_format +\
                    ('{:' + format_mapping[item] + '}')\
                    .format(str(trans_dict[item]))
            print string_format

        return

    elif args.format == 'csv':
        try:
            writer = csv.writer(sys.stdout)
            writer.writerow(request_field)
            for txn_id in tsctids:
                trans_dict = get_trans_info(web_client, txn_id,
                                            info_fields_mapping)
                result = []
                for _, item in enumerate(request_field):
                    result.append(trans_dict[item])
                writer.writerow(result)
        except csv.Error as e:
            raise CliException(e)

    elif args.format == 'json' or args.format == 'yaml':
        json_dict = []
        for txn_id in tsctids:
            trans_dict = get_trans_info(web_client, txn_id,
                                        info_fields_mapping)
            json_dict.append(trans_dict)
        if args.format == 'json':
            print json.dumps(json_dict)
        else:
            print yaml.dump(json_dict, default_flow_style=False)

    else:
        raise CliException(
            "unknown format option: {}".format(args.format))


def get_trans_info(web_client, txn_id, info_fields_mapping=None):
    trans_info = web_client.get_transaction(txn_id)
    trans_info_specified = {}
    if info_fields_mapping is not None:
        for k, field in info_fields_mapping.iteritems():
            field_split = field.split(".")
            if len(field_split) == 1:
                trans_info_specified[k] = trans_info[field_split[0]]
            elif len(field_split) == 2:
                update = trans_info[field_split[0]]
                trans_info_specified[k] = update[field_split[1]]
            elif len(field_split) > 2:
                raise CliException(
                    "unknown format info_fields_mapping: {}"
                    .format(info_fields_mapping))
    else:
        trans_info_specified['TRANS'] = trans_info['Identifier']
        trans_info_specified['BLOCK'] = trans_info['InBlock']
        trans_info_specified['Status'] = trans_info['Status']
        trans_info_specified['TXNTYPE'] = trans_info['TransactionType']

    return trans_info_specified
