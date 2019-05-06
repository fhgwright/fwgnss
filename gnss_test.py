#!/usr/bin/env python
"""Test program for GNSS Extracter/Parser/Decoder/Formatter modules."""

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

from fwgnss.parse import hemisphere as parse_hemisphere
from fwgnss.format import hemisphere as format_hemisphere

Extracter = parse_hemisphere.Extracter
Parser = parse_hemisphere.Parser
Decoder = parse_hemisphere.Decoder
Formatter = format_hemisphere.Formatter


def ParseArgs(argv):
  """Parse arguments from command line.

  Args:
    argv: list of arguments

  Returns:
    parse result
  """
  parser = argparse.ArgumentParser(description='Process NMEA-0183 data')
  parser.add_argument('-i', '--input', type=argparse.FileType(mode='rb'))
  return parser.parse_args(argv)


def GotItem(item, fname, parser, decoder, formatter):
  """Breakpoint spot for debugging."""
  parsed = parser.Parse(item)
  if parsed:
    decoded = decoder.Decode(item)
  else:
    decoded = None
  if item.parse_error:
    print('Parse error in %s:' % fname, item.parse_error, file=sys.stderr)
  if item.decode_error:
    print('Decode error in %s:' % fname, item.decode_error, file=sys.stderr)
  formatter.Put(item)
  return parsed, decoded


def main(argv):
  """Main function."""
  parsed_args = ParseArgs(argv[1:])
  extracter = Extracter(parsed_args.input)
  parser = Parser()
  decoder = Decoder()
  formatter = Formatter()
  if parsed_args.input:
    fname = parsed_args.input.name
    for item in extracter.GetItems():
      _ = GotItem(item, fname, parser, decoder, formatter)
      _ = item.Contents()
      _ = item.Summary()
      _ = item.LogText()
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))  # pragma: no cover
