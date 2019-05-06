#!/usr/bin/env python
"""Program to decode and print GNSS data."""

#                      Copyright (c) 2019
#                   Frederick H. G. Wright II
#                          fw@fwright.net
#
#        The information in this software is subject to change
#   without notice and should not be construed as a commitment  #
#   by Frederick H. G. Wright II, hereafter known as "author".
#   The author makes no representations about the suitability
#   of this software for any purpose.  It is supplied "As Is"
#   without expressed or implied  warranty.
#
#        This software may be copied or distributed for any
#   noncommercial purpose, with the inclusion of this notice,
#   and provided that any modifications are clearly identified
#   as such and are accompanied by the original unmodified
#   software.

from __future__ import absolute_import, print_function, division

import argparse
import sys

from fwgnss.format import nmea as format_nmea
from fwgnss.format import hemisphere as format_hemisphere

VENDOR_MODULES = [format_hemisphere]


def ParseArgs(argv):
  """Parse arguments from command line.

  Args:
    argv: list of arguments

  Returns:
    parse result
  """
  parser = argparse.ArgumentParser(
      description='Decode NMEA-0183 data (with possible binary messages)'
      )
  parser.add_argument('-g', '--show-gps-time', action='store_true',
                      help='show GPS time rather than UTC')
  parser.add_argument('-i', '--input', type=argparse.FileType(mode='rb'),
                      required=True)
  parser.add_argument('-o', '--output', type=argparse.FileType(mode='w'))
  parser.add_argument('-r', '--dump-raw-binary', action='store_true',
                      help='include hex dump of binary data')
  parser.add_argument('-s', '--stop-on-errors', action='store_true')
  parser.add_argument('-S', '--stop-on-warnings', action='store_true')
  parser.add_argument('-f', '--filter', help='item type filter list')
  parser.add_argument('-q', '--hide-warnings', action='store_true',
                      help='hide warnings from stderr')
  parser.add_argument('-Q', '--exclude-warnings', action='store_true',
                      help='exclude warnings from output')
  parser.add_argument('--format-level', type=int, help='format-level value')
  return parser.parse_args(argv)


def GetFormatClass(vendor_arg=''):
  """Get proper formatter for specified vendor."""
  vendor = vendor_arg.capitalize()
  for module in VENDOR_MODULES:
    if vendor in module.VENDORS:
      break
  else:
    module = format_nmea
  return module.Formatter


def GetFilterList(arg, parse_map):
  """Convert filter arg to parser set."""
  result = set()
  for item in arg.split(','):
    item_l = item.split('.')
    if len(item_l) == 1:
      msgclass = 'NMEA'
      msgtype = item.upper()
    elif len(item_l) == 2:
      msgclass = item_l[0].upper()
      try:
        msgtype = int(item_l[1])
      except ValueError:
        msgtype = item_l[1].upper()
    else:
      raise ValueError
    result |= set([parse_map[msgclass].GetParser(msgtype)])
  return result


def main(argv):
  """Main function."""
  parsed_args = ParseArgs(argv[1:])

  report_errors = not (parsed_args.output and parsed_args.output.isatty())

  format_class = GetFormatClass('Geneq')
  formatter = format_class(parsed_args.input)
  formatter.dump_raw_data = parsed_args.dump_raw_binary
  formatter.show_gps_time = parsed_args.show_gps_time
  extracter = formatter.extracter
  extracter.AllowComments()

  if parsed_args.filter:
    formatter.filter = GetFilterList(parsed_args.filter,
                                     formatter.extracter.parse_map)
  if parsed_args.format_level is not None:
    formatter.SetFormatLevel(parsed_args.format_level)
  formatter.stop_on_error = parsed_args.stop_on_warnings
  formatter.hide_warnings = parsed_args.hide_warnings
  formatter.exclude_warnings = parsed_args.exclude_warnings

  pdb_module = sys.modules.get('pdb')
  if pdb_module:
    lb = 0  # pylint: disable=invalid-name
    pdb_module.set_trace()
    extracter.linebreak = lb  # Concise name for typing

  for item in extracter.GetItems():
    try:
      formatter.Put(item)
    # Catch all parse/decode/format exceptions here
    except Exception:  # pylint: disable=broad-except
      if parsed_args.stop_on_errors or parsed_args.stop_on_warnings:
        raise
    lines = formatter.Get()
    if parsed_args.output:
      try:
        for line in lines:
          print(line, file=parsed_args.output)
      except IOError:
        return 1
    errors = formatter.GetErrors()
    if report_errors:
      for line in errors:
        print(line, file=sys.stderr)

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))  # pragma: no cover
