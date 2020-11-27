#!/usr/bin/env python
"""Program to split mixed NMEA/binary GNSS data into separate files."""

#                      Copyright (c) 2020
#                   Frederick H. G. Wright II
#                          fw@fwright.net
#
#        The information in this software is subject to change
#   without notice and should not be construed as a commitment
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
import re
import sys

try:
  reduce
except NameError:
  from functools import reduce  # pylint: disable=redefined-builtin

from fwgnss.parse import combined

DUMMY_TIME = '??????.??'


def CsvInts(values):
  """Return list of ints from CSV string."""
  return list(map(int, values.split(',')))


def CsvTimes(values):
  """Return list of time ranges from CSV string."""
  result = []
  for entry in values.split(','):
    times = entry.split('-')
    end = times[1] if len(times) > 1 else times[0]
    result.append([float(times[0]), float(end)])
  return result


def EncodeTime(time, frac_digits=2):
  """Format a time as HHMMSS.ff."""
  strip = 6 - frac_digits if frac_digits else 7
  rnd = 10 ** (9 - frac_digits) // 2
  return time.strftime('%H%M%S.%f', rnd)[:-strip]


def CheckTime(tvalue, trange):
  """See if time is within range, with simple wraparound handling."""
  if trange[1] < trange[0]:
    return trange[1] <= tvalue <= trange[0]
  return trange[0] <= tvalue <= trange[1]


def CheckTimeList(tvalstr, tlist):
  """See if time is within any range in list."""
  try:
    tvalue = float(tvalstr)
  except ValueError:
    return False
  for trange in tlist:
    if CheckTime(tvalue, trange):
      return True
  return False


def GetBundledNmeaData(extracter, decoder):
  """Get groups of NMEA data corresponding to one GPGGA sentence,
  with GxGSA content reported for filtering.

  Args:
    extracter: extracter object to read from

  Returns:
    iterator of tuples of (time, nmea list, GxGSA data, other data)
  """
  nmea_time = ''
  nmea_data = []
  other_data = []
  gsa_data = []
  OTHER_TYPES = (  # pylint: disable=invalid-name
      combined.ControlItem, combined.BinaryItem
      )
  for item in extracter.GetItems():

    if isinstance(item, OTHER_TYPES):
      other_data.append(item)
      continue

    if not isinstance(item, combined.Sentence):
      continue

    data = item.data
    stype = data[0]
    if stype == 'GPGGA':
      if gsa_data:
        yield (nmea_time, nmea_data, gsa_data, other_data)
        nmea_data = []
        other_data = []
        gsa_data = []
      parsed = combined.Parser.Parse(item)
      decoded = parsed and decoder.Decode(item)
      nmea_time = EncodeTime(decoded.time) if decoded else ''
    elif stype in ['GPGSA', 'GNGSA', 'GLGSA'] and not gsa_data:
      gsa_data = data
    nmea_data.append(item)
  if nmea_data or other_data:
    yield (nmea_time, nmea_data, gsa_data, other_data)


def GetFilteredNmeaData(  # pylint: disable=too-many-branches,too-many-locals
    extracter, decoder, pattern, need_match
    ):
  """Get NMEA lines, with GxGSA filtering.

  Args:
    extracter: extracter object to read from
    pattern: str GxGSA match pattern
    need_match: int min matching between mismatches

  Returns:
    iterator of filtered entries, with type code
  """
  test = [re.compile(x) for x in pattern.split(',')]
  failing = 0
  saved = []

  def _Matcher(current, pair):
    return current and pair[1].match(pair[0])

  # pylint: disable=too-many-nested-blocks
  for nmea_time, nmea_list, gsa_data, other in GetBundledNmeaData(
      extracter, decoder
      ):
    # If filtering, ignore anything without GSA data for comparison
    if not gsa_data and pattern:
      continue
    match_list = list(zip(gsa_data[1:], test))
    matched = reduce(_Matcher, match_list, True)
    if matched:
      if not failing:
        for item in nmea_list + other:
          yield nmea_time, item
      else:
        failing -= 1
        saved.append((nmea_time, nmea_list, other))
        if not failing:
          for s_nmea_time, s_nmea, s_other in saved:
            for item in s_nmea + s_other:
              yield s_nmea_time, item
          saved = []
    else:
      failing = need_match
      # Don't filter other
      saved.append((nmea_time, nmea_list, other))
      for s_nmea_time, s_nmea, s_other in saved:
        yield s_nmea_time, None  # Dummy item to break it up
        for item in s_other:
          yield s_nmea_time, item
      saved = []
  # Dump any valid entries at the end (if need_match not met)
  for s_nmea_time, s_nmea, s_other in saved:
    for item in s_nmea + s_other:
      yield s_nmea_time, item


def DumpLogs(ofile, log_time, control_log, binary_log):
  """Dump accumulated logs.

  Args:
    ofile: file for output
    log_time: timestamp from NMEA sentence
    control_log: list of control items
    binary_log: list of binary messages
  """
  if control_log:
    for control in control_log:
      try:
        print('%s> %s' % ((log_time or DUMMY_TIME), control), file=ofile)
      except IOError:
        pass
    control_log[:] = []
  if binary_log:
    try:
      print('%s: %s' % ((log_time or DUMMY_TIME), ', '.join(binary_log)),
            file=ofile)
    except IOError:
      pass
    binary_log[:] = []


class ArgParser(object):  # pylint: disable=too-few-public-methods
  """Class for parsing command-line arguments."""
  PARSER = argparse.ArgumentParser(
      description='Split GNSS data, NMEA vs. binary'
      )
  PARSER.add_argument('-i', '--input', type=argparse.FileType(mode='rb'),
                      required=True)
  PARSER.add_argument('-p', '--pattern', type=str, default='')
  PARSER.add_argument('-m', '--min-match', type=int, default=30)
  PARSER.add_argument('-o', '--output', type=argparse.FileType(mode='w'))
  PARSER.add_argument('-b', '--binary_out', type=argparse.FileType(mode='wb'))
  PARSER.add_argument('-l', '--log_other', type=argparse.FileType(mode='w'))
  PARSER.add_argument('-s', '--strip-crs', action='store_true')
  PARSER.add_argument('--include-bin', type=CsvInts)
  PARSER.add_argument('--exclude-bin', type=CsvInts)
  PARSER.add_argument('--include-times', type=CsvTimes)
  PARSER.add_argument('--exclude-times', type=CsvTimes)
  PARSER.add_argument('--exclude-control', action='store_true')

  @classmethod
  def Parse(cls, argv):
    """Parse arguments from supplied argv list."""
    return cls.PARSER.parse_args(argv)


# pylint: disable=too-many-branches,too-many-statements,too-many-locals
def main(argv):
  """Main function."""
  parsed_args = ArgParser.Parse(argv[1:])
  include_bin = parsed_args.include_bin and set(parsed_args.include_bin)
  exclude_bin = (set(parsed_args.exclude_bin) if parsed_args.exclude_bin
                 else set())
  include_times = parsed_args.include_times
  exclude_times = parsed_args.exclude_times
  control_log = []
  binary_log = []
  log_time = ''
  extracter = combined.Extracter(parsed_args.input)
  decoder = combined.Decoder()
  nmea_break = None
  lb = 0  # pylint: disable=invalid-name

  pdb_module = sys.modules.get('pdb')
  if pdb_module:
    pdb_module.set_trace()
    extracter.linebreak = lb  # Concise name for typing

  if parsed_args.input:  # pylint: disable=too-many-nested-blocks
    try:
      for nmea_time, item in GetFilteredNmeaData(
          extracter, decoder, parsed_args.pattern, parsed_args.min_match):

        if nmea_time == nmea_break:
          if pdb_module:
            pdb_module.set_trace()

        if log_time != nmea_time or not item:
          DumpLogs(parsed_args.log_other, log_time, control_log, binary_log)
          log_time = nmea_time

        if isinstance(item, combined.Sentence):
          DumpLogs(parsed_args.log_other, log_time, control_log, binary_log)
          if exclude_times:
            excluded = CheckTimeList(nmea_time, exclude_times)
            if excluded:
              continue
          if include_times:
            included = CheckTimeList(nmea_time, include_times)
            if not included:
              continue
          if parsed_args.output:
            try:
              if parsed_args.strip_crs:
                parsed_args.output.write(item.Contents().replace('\r', ''))
              else:
                parsed_args.output.write(item.Contents())
            except IOError:
              pass
          continue

        if isinstance(item, combined.ControlItem):
          if parsed_args.log_other and not parsed_args.exclude_control:
            control_log.append(item.LogText())
          continue

        if isinstance(item, combined.BinaryItem):
          msgtype = item.msgtype
          if include_bin is not None and not msgtype in include_bin:
            continue
          if exclude_bin and msgtype in exclude_bin:
            continue
          if parsed_args.binary_out:
            parsed_args.binary_out.write(item.Contents())
          if parsed_args.log_other:
            binary_log.append(item.LogText())
          continue

    except KeyboardInterrupt:
      print()

    DumpLogs(parsed_args.log_other, log_time, control_log, binary_log)

  for out in [parsed_args.output,
              parsed_args.binary_out, parsed_args.log_other]:
    if not out:
      continue
    try:
      out.close()
    except IOError:
      pass
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))  # pragma: no cover
