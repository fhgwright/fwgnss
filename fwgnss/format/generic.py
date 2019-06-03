"""Module for generic formatting of GNSS data into human-friendly form."""

#                      Copyright (c) 2019
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

from ..datadefs import BindDictFuncs
from ..debuggable import Debuggable
from ..parse import generic  # For pylint-placating dummy defs
from ..datetime import xdatetime


class Error(Exception):
  """Base class for all exceptions defined in this module."""
  pass  # pylint: disable=unnecessary-pass


class ParseError(Error):
  """Item was not parsed correctly."""
  pass  # pylint: disable=unnecessary-pass


class DecodeError(Error):
  """Item was not decoded correctly."""
  pass  # pylint: disable=unnecessary-pass


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class Formatter(Debuggable):
  """Base class for formatter objects."""
  SPACES = '              '

  FORMATTER_DICT = {}

  # Formatter levels to allow reproducing older behavior
  FMT_ORIGINAL = 0    # Earliest version with retained results
  FMT_UPDATED = 1     # With some updates
  FMT_WAAS_BASIC = 2  # Introduce WAAS type decodes

  # Dummy defs to placate pylint, overridden in subclasses
  EXTRACTER = generic.Extracter
  PARSER = generic.Parser
  DECODER = generic.Decoder

  def __init__(self, infile=None):
    self.show_gps_time = False
    self.dump_raw_data = False
    self._output = []
    self._errors = []
    self._last_summary = None
    self.extracter = self.EXTRACTER(infile)
    self.decoder = self.DECODER()
    self.formatter_dict = BindDictFuncs('FORMATTER_DICT', self)
    self.filter = set()
    self.stop_on_error = False     # Turn parse/decode errors into exceptions
    self.hide_warnings = False     # Exclude warnings from stderr
    self.exclude_warnings = False  # Exclude warnings from output
    self.fmt_level = 999999  # Allow everything by default

  def SetFormatLevel(self, level):
    """Set formatter compatibility level."""
    self.fmt_level = level

  def Put(self, item):  # pylint: disable=too-many-branches
    """Process one item, added formatted result to list(s)."""
    if self.filter:
      parser = item.PARSE_CLASS.GetParser(item.msgtype)
      if parser not in self.filter:
        return
    parsed = self.PARSER.Parse(item)  # Need parser set up for DESCRIPTION
    summary = item.Summary(full=True)
    self._last_summary = summary
    if summary:
      self.Send(0, summary)
    if item.parse_error:
      self.SendError(2, item.parse_error)
    if self.dump_raw_data:
      self.DumpRaw(4, item)
    if item.parse_error and self.stop_on_error:
      raise ParseError(item.parse_error)
    if not parsed:
      return
    decoded = self.decoder.Decode(item)
    formatter = self.formatter_dict.get(item.parser)
    # If not found, try parent classes
    if not formatter:
      for parser in item.parser.__mro__:
        formatter = self.formatter_dict.get(parser)
        if formatter:
          break
    if item.decode_error:
      err = item.decode_error
      if isinstance(err, str):
        self.SendError(2, err)
      elif isinstance(err, tuple):
        self.SendError(2, err[0])
        if formatter:
          formatter(item, err[1], error=True)
      else:
        self.SendError(2, 'Unexpected decode error type')
      if self.stop_on_error:
        raise DecodeError(item.decode_error)
    if not decoded:
      return
    if formatter:
      formatter(item)
    return

  def Send(self, indent, text):
    """Send text to output list."""
    self._output.append(self.SPACES[:indent] + text)

  def SendError(self, indent, text):
    """Send error to output list."""
    if text.startswith('Residual mismatch in '):
      return  ### Temp hide this
    if self.fmt_level < self.FMT_UPDATED and text.startswith('Extra comma in'):
      text = text.replace(' GPRMC', '')
    if not self.exclude_warnings:
      self._output.append(self.SPACES[:indent] + '*** ' + text)
    if not self.hide_warnings:
      if self._last_summary:
        self._errors.append('%s: %s' % (text, self._last_summary))
      else:
        self._errors.append(text)

  @staticmethod
  def DumpRaw(indent, item):
    """Dummy raw dump, overridden in subclasses."""
    _, _ = indent, item

  def Get(self):
    """Get and clear pending output."""
    result = self._output
    self._output = []
    return result

  def GetErrors(self):
    """Get and clear any errors."""
    result = self._errors
    self._errors = []
    return result

  @staticmethod
  def EncodeTime(time, frac_digits=2):
    """Format a time as HH:MM:SS."""
    strip = 6 - frac_digits if frac_digits else 7
    rnd = 10 ** (9 - frac_digits) // 2
    return time.strftime('%H:%M:%S.%f', rnd)[:-strip]

  @staticmethod
  def EncodeDateTime(dtime, frac_digits=2, fixed_leap=None):
    """Format a date/time as YYYY-MM-DD HH:MM:SS."""
    strip = 6 - frac_digits if frac_digits else 7
    rnd = 10 ** (9 - frac_digits) // 2
    return dtime.strftime('%Y-%m-%d %H:%M:%S.%f',
                          roundofs=rnd, fixed_leap=fixed_leap)[:-strip]

  def GetDateTimeStr(self, dtime, frac_digits=2):
    """Format a date/time as either GPS or UTC date/time."""
    if self.show_gps_time:
      return self.EncodeDateTime(dtime, frac_digits,
                                 fixed_leap=xdatetime.GPS_LEAP_OFFSET) + ' GPS'
    return self.EncodeDateTime(dtime, frac_digits) + ' UTC'

  def GetWeekTowStr(self, dtime, frac_digits=3):
    """Format a date/time as a GPS week/sec."""
    dtime_str = self.GetDateTimeStr(dtime, frac_digits=frac_digits)
    week, secs, nanos = dtime.gps_weeks_secs_nanos(roundofs=0)
    second = secs + nanos / 1.0E9
    return 'GPS week/sec = %d/%.3f (%s)' % (week, second, dtime_str)

  @staticmethod
  def EncodeGPSDateTime(dtime, frac_digits=2):
    """Format a date/time as a GPS-style week/sec."""
    strip = 6 - frac_digits if frac_digits else 7
    rnd = 10 ** (9 - frac_digits) // 2
    try:
      week, secs, nanos = dtime.gps_weeks_secs_nanos(roundofs=rnd)
    except AttributeError:
      return None
    return ('%d/%d.%06d' % (week, secs, nanos // 1000))[:-strip]

  @staticmethod
  def EncodeAlt(value, units='M'):
    """Format an altitude, with a units specification."""
    if units == 'M':
      return '%.3fm/%.3f\'' % (value, value / .3048)
    return '%.3f%s' % (value, units)

  @staticmethod
  def DecodeChar(char, map_dict, default='???'):
    """Decode a character, based on a map."""
    return '%s (%s)' % (char, map_dict.get(char, default))

  @staticmethod
  def DecodeNum(num, map_dict, default='???'):
    """Decode a number, based on a map."""
    return '%d (%s)' % (num, map_dict.get(num, default))

  @staticmethod
  def DecodeEnum(value, map_list):
    """Decode an enum, based on a name map."""
    try:
      return '%d (%s)' % (value, map_list[value])
    except IndexError:
      return '%d (???)' % value

  @staticmethod
  def ExtractBits(value, names, group=1):
    """Extract a series of named bits from a value."""
    bit = 1
    num = 0
    result = []
    current = []
    for name in names:
      if value & bit and name:
        current.append((bit, name))
      bit <<= 1
      num += 1
      if num % group == 0 and current:
        result.append(current)
        current = []
    if current:
      result.append(current)
    return result

  def DumpBits(self,  # pylint: disable=too-many-arguments
               indent, header, fmt, value, names, group=1):
    """Format a series of bits by names."""
    decode = self.ExtractBits(value, names, group)
    if not decode:
      self.Send(indent, (header + fmt) % value)
      return
    self.Send(indent, (header + fmt + ':') % value)
    fmt += ' = %s'
    for grp in decode:
      line = ', '.join([fmt % (bit, name) for bit, name in grp])
      self.Send(indent + 4, line)

  @staticmethod
  def ExtractNibbles(value, names):
    """Extract a series of nibbles from a value."""
    result = []
    for name in names:
      if name:
        result.append((value & 0xF, name))
      value >>= 4
    return result

  def DumpNibbles(self, indent, header, value, names):
    """Foramt a value as nibbles."""
    decode = self.ExtractNibbles(value, names)
    if not decode:
      self.Send(indent, header % value)
      return
    self.Send(indent, (header + ':') % value)
    for count, name in decode:
      self.Send(indent + 2, '%2d %s' % (count, name))

  def DumpULongs(self, indent, name, data):
    """Format a series of unsigned longs."""
    out_list = [name + ':']
    for val in data:
      out_list.append('%.08X' % val)
    self.Send(indent, ' '.join(out_list))

  @staticmethod
  def FormatTuple(fmt, data):
    """Format a named tuple as specified."""
    return [fmt % x for x in zip(data._fields, data)]


class BinaryFormatter(Formatter):
  """Base class for generic binary message formatter object."""

  def __init__(self, infile=None):
    super(BinaryFormatter, self).__init__(infile)
    self.little_endian = self.EXTRACTER.ENDIANNESS == 'little'
    self.IsBinary = self.EXTRACTER.IsBinary  # pylint: disable=invalid-name

  def DumpRaw(self, indent, item):
    """Dump raw data if binary."""
    if not self.IsBinary(item):
      return
    for line in self.FormatRawData(item.data, item.length, self.little_endian):
      self.Send(indent, line)

  def DumpBitString(self, indent, name, bits):
    """Dump BitString item."""
    digits = (bits.nbits + 3) // 4
    self.Send(indent, '%s: %0*X' % (name, digits, bits.data))

  def DumpBitStrings(self, indent, nlist, dlist):
    """Dump list of BitStrings labeled by list of names."""
    for name, data in zip(nlist, dlist):
      self.DumpBitString(indent, name, data)

  @staticmethod
  def FormatRawData(data, datalen, little_endian=False):
    """Format raw hex dump."""
    adrfmt = '%.04X' if datalen > 4096 else '%.03X'
    idx, buf = 0, iter(bytearray(data))
    result = []
    while idx < datalen:
      num = min(16, datalen - idx)
      dlist = [adrfmt % idx, '']
      for ofs in range(num):
        if ofs % 4 == 0:
          dlist.append('')
        dlist.append('%.02X' % next(buf))
      if little_endian:
        for ofs in range(num, 16):
          if ofs %4 == 0:
            dlist.append('')
          dlist.append('  ')
        dlist.reverse()
      result.append(' '.join(dlist))
      idx += num
    return result
