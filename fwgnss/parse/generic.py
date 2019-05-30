"""Generic GNSS parsing base."""

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

import collections
import sys

from .. import params as gnss
from ..datetime import xdatetime


class Constants(object):  # pylint:disable=too-few-public-methods
  """Class which holds various constant definitions."""

  SECONDS_PER_DAY = xdatetime.SECONDS_PER_DAY
  SECONDS_PER_WEEK = xdatetime.SECONDS_PER_WEEK
  GPS_LEAPS = xdatetime.GPS_LEAP_OFFSET

  # System ID codes (NMEA and internal)
  SYSTEM_ID_GPS = 1
  SYSTEM_ID_GLONASS = 2
  SYSTEM_NAMES = ('GPS', 'GLONASS')  # Beware zero-based vs. one-based
  SYSTEM_DECODE = {1: 'GPS', 2: 'GLONASS'}

  # Satellite type codes (internal)
  SAT_TYPE_GPS = 0
  SAT_TYPE_SBAS = 1
  SAT_TYPE_GLONASS = 2
  SAT_TYPE_LETTERS = ('G', 'S', 'R')

  # Signal type codes (internal)
  SIGNAL_L1CA = 0
  SIGNAL_L1P = 1
  SIGNAL_L2P = 2
  SIGNAL_G1 = 3
  SIGNAL_G2 = 4
  SIGNAL_NAMES = ('L1 C/A', 'L1P', 'L2P', 'G1', 'G2')

  # Wavelengths by signal type
  GPS_L1_WAVELENGTH = gnss.GPS_L1_WAVELENGTH
  GPS_L2_WAVELENGTH = gnss.GPS_L2_WAVELENGTH
  GLO_L1_WAVELENGTHS = gnss.GLO_L1_WAVELENGTHS
  GLO_L2_WAVELENGTHS = gnss.GLO_L2_WAVELENGTHS
  SIGNAL_WAVELENGTH = (
      GPS_L1_WAVELENGTH,
      GPS_L1_WAVELENGTH,
      GPS_L2_WAVELENGTH,
      None,  # Knum-dependent
      None,  # Knum-dependent
      )


class BaseItem(object):  # pylint:disable=too-many-instance-attributes
  """Base class for extracted items."""
  # The IV/CV methods expect that class "variables" are all upper case,
  # and that instance variables are all lower case.
  PARSE_CLASS = None
  _DEBUG_EXCLUDE = set(['IV', 'CV', '_DEBUG_EXCLUDE'])

  __slots__ = ('data', 'length', 'msgtype', 'subtype',
               'parser', 'parsed', 'parse_error',
               'decoded', 'decode_error')

  def __init__(self, data=None, length=None, msgtype=None):
    self.data = data
    self.length = length or len(data)
    self.msgtype = msgtype
    self.subtype = None
    self.parser = None
    self.parsed = None
    self.parse_error = None
    self.decoded = None
    self.decode_error = None

  @staticmethod
  def Contents():
    """Return full contents of item."""
    return None

  @staticmethod
  def Summary(full=False):
    """Return summary text for item."""
    _ = full

  @staticmethod
  def LogText():
    """Return item text for logging."""
    return None

  def IV(self):  # pylint: disable=invalid-name
    """Get dict of instance variables (for debugging)."""
    # Uses the naming convention for filtering
    result = {}
    for name in dir(self):
      if not name.startswith('__') and name == name.lower():
        result[name] = getattr(self, name)
    return result

  @classmethod
  def CV(cls):  # pylint: disable=invalid-name
    """Get dict of class variables (for debugging)."""
    # Uses the naming convention for filtering
    result = {}
    for name in dir(cls):
      if (not name.startswith('__') and name == name.upper()
          and name not in cls._DEBUG_EXCLUDE):
        result[name] = getattr(cls, name)
    return result

class ErrorItem(BaseItem):
  """Class for unrecognizable items."""

  __slots__ = ()


class Item(BaseItem):
  """Base class for non-error extracted items."""

  __slots__ = ()


class TextItem(Item):
  """Base class for text-based extracted items."""
  # Various EOL formats, used by multiple item types
  CR_IN = b'\r'
  LF_IN = b'\n'
  EOL_IN = CR_IN + LF_IN
  ALL_EOL_IN = [EOL_IN, LF_IN, CR_IN]

  TEXT_ENCODING = 'ascii'

  __slots__ = ()


class ResponseItem(Item):
  """Base class for command-response extracted items."""

  __slots__ = ()


class TextResponseItem(ResponseItem, TextItem):
  """Base class for text-based command-response extracted items."""

  __slots__ = ()


class Comment(TextItem):
  """Class for comment lines."""
  PREFIX_IN = b'#'

  __slots__ = ()

  def Contents(self):
    return self.data

  def Summary(self, full=False):
    return self.data

  def LogText(self):
    return self.data


class Extracter(object):  # pylint: disable=too-many-instance-attributes
  """Base class for extracters."""
  LINE_MAX = 500  # Generous limit - just defends against non-CRLF data

  # Dummy defs to placate pylint, overridden in subclasses
  ENDIANNESS = None

  def __new__(cls, infile=None):
    _ = infile
    self = super(Extracter, cls).__new__(cls)
    self.extracter_list = []
    self.extracters = []
    self.parse_map = {}
    return self

  def __init__(self, infile=None):
    self.input = infile
    self.line = b''
    self.linenum = 0       # For debugging
    self.linebreak = 0     # To stop on line for debugging
    self.skipped = b''     # Unrecognized data we skipped
    self.extended = False  # True if we needed to extend line to get an item
    self.extracter_list = self.extracter_list  # Placate pylint 3
    self.parse_map = self.parse_map            # Ditto
    self.BindExtracters()

  def AddExtracter(self, cls, name):
    """Add a new extracter method to list, by name."""
    func = getattr(cls, name, None)
    if not func:
      return
    self._AddExtracter(cls, name, func)

  def _AddExtracter(self, cls, name, func):
    """Add a new extracter method to list, by method object."""
    for num, ent in enumerate(self.extracter_list):
      # Filter out duplicates
      if ent[2] == func:
        return
      # Filter out overridden methods from parent classes
      if isinstance(self, ent[0]) and name == ent[1]:
        self.extracter_list.pop(num)
        break
    # Initially, we reverse the order to compensate for the reversed order
    # in the calls from __init__().  After the initial BindExtracters()
    # call, subsequent additions are at the end.
    if self.extracters:
      self.extracter_list.append((cls, name, func))
    else:
      self.extracter_list.insert(0, (cls, name, func))

  def BindExtracters(self):
    """Derive a list of bound extracter methods from extracter_list."""
    self.extracters = [x[2].__get__(self, x[0]) for x in self.extracter_list]

  def MergeExtracters(self, other):
    """Merge list of extracters from other extracter into this one."""
    if not isinstance(other, Extracter):
      raise ValueError
    for cls, name, func in other.extracter_list:
      self._AddExtracter(cls, name, func)
    self.BindExtracters()

  def GetLine(self, maxlen=LINE_MAX):
    """Get another line of data from input."""
    data = self.input.readline(maxlen)
    if not data:
      return False
    if data.endswith(TextItem.LF_IN):
      self.linenum += 1
      if self.linenum == self.linebreak:
        pdb_module = sys.modules.get('pdb')
        if pdb_module:
          pdb_module.set_trace()
    if self.line:
      self.line += data
      self.extended = True
    else:
      self.line = data
      self.extended = False
    return True

  def GetEOL(self):
    """Determine lengths of line and EOL."""
    # Ordinarily, the first EOL is at the end of the buffer.  But if we've
    # extended the buffer, then we need to search for it.
    line = self.line
    if self.extended:
      pos = self.line.find(TextItem.LF_IN) + 1
      if pos > 0:
        if pos < len(line):
          line = line[:pos]
        else:
          self.extended = False  # Back to normal if at end of buffer
    for end in TextItem.ALL_EOL_IN:
      if line.endswith(end):
        endlen = len(end)
        return len(line) - endlen, endlen
    return len(line), 0  # If unterminated line

  def _GetErrorItem(self):
    """Get an error item for skipped data, and reset skipped."""
    item = ErrorItem(self.skipped)
    self.skipped = b''
    return item

  def GetItems(self):
    """Generator to return extracted items."""
    while True:
      if not self.line:
        if not self.GetLine():
          if self.skipped:
            yield self._GetErrorItem()
          return
      item = None
      for extracter in self.extracters:
        item, consumed = extracter()
        if item:
          break
      if item:
        if self.skipped:
          yield self._GetErrorItem()
        yield item
        self.line = self.line[consumed:]
        continue
      if self.line:
        self.skipped += self.line[:1]
        self.line = self.line[1:]
        continue
      if self.skipped:
        yield self._GetErrorItem()

  @staticmethod
  def GetText(data):
    """Convert data from bytes to string, if needed."""
    if isinstance(data, str):
      return data
    return data.decode(TextItem.TEXT_ENCODING)

  @staticmethod
  def IsBinary(item):
    """Return True if item is binary."""
    _ = item
    return False

  def AllowComments(self):
    """Enable comment-line recognition in this Extracter."""
    self.MergeExtracters(CommentExtracter())


class CommentExtracter(Extracter):
  """Class for comment-line extracter."""
  def __new__(cls, infile=None):
    self = super(CommentExtracter, cls).__new__(cls, infile)
    self.AddExtracter(CommentExtracter, 'ExtractComment')
    return self

  def ExtractComment(self):
    """Extracter for comment lines."""
    if  not self.line.startswith(Comment.PREFIX_IN):
      return None, 0
    length, endlen = self.GetEOL()
    if not endlen:
      return None, 0
    data = self.GetText(self.line[:length])
    return Comment(data=data, length=length), length + endlen


class Parser(object):
  """Base class for item parsers."""

  @classmethod
  def GetParser(cls, msgtype, subtype=None):
    """Get parser for this message type (and possibly subtype)."""
    _, _ = msgtype, subtype

  @classmethod
  def Parse(cls, item):
    """Parse the item, returning and storing the result."""
    parse_class = item.PARSE_CLASS
    parser = parse_class and parse_class.GetParser(item.msgtype)
    item.parser = parser
    parsed = parser and parse_class.ParseData(parser, item)
    item.parsed = parsed
    return parsed

  @staticmethod
  def ParseData(parser, item):
    """Return parsed object for this item's data."""
    return parser.Parse(item)

  class ParseItem(object):  # pylint: disable=too-few-public-methods
    """Base class for type-specific parsers."""

    @classmethod
    def ThisParser(cls, subtype=None):
      """Obtain subtype-specific parser for this item."""
      _ = subtype
      return cls


class Decoder(object):
  """Base class for item decoders."""
  DECODER_DICT = {}

  def __init__(self):
    self.last_time = None
    self.last_dtime = None

  SatResidual = collections.namedtuple('Residual', 'sat type num value')
  SatView = collections.namedtuple('SatView', 'sat type num')

  def Decode(self, item, ignore_error=False):
    """Return and store the decoded version of this item."""
    decoder = self.DECODER_DICT.get(item.parser)
    if decoder:
      if ignore_error:
        try:
          decoded = decoder(self, item)
        # Any exception aborts decode
        except:  # pylint: disable=bare-except
          decoded = None
      else:
        decoded = decoder(self, item)
      item.decoded = decoded
      return decoded
    return None

  def MakeTimeHMSN(self,  # pylint: disable=too-many-arguments
                   hour, minute, second, nanosecond, store=True):
    """Convert HMSN time to time object, and optionally update datetime."""
    time = xdatetime.time(hour, minute, second, nanosecond)
    if store:
      self.last_time = time
      if self.last_dtime:
        # Once date/time is known, time-only value can update date/time
        self.last_dtime = xdatetime.datetime.from_datetime_time(
            self.last_dtime, time
            )
    return time

  def MakeDateTimeYMDT(self,  # pylint: disable=too-many-arguments
                       year, month, day, time, store=True):
    """Convert YMDT to datetime object, and optionally store."""
    if year < 100:
      if year < 80:
        year += 2000
      else:
        year += 1900
    return self._ReturnDateTime(xdatetime.datetime(
        year, month, day,
        time.hour, time.minute, time.second, time.nanosecond), store)

  def _ReturnDateTime(self, dtime, store=True):
    if store:
      self.last_dtime = dtime
    return dtime

  def DecodeGPSTime(self, week, sec_of_week, store=True):
    """Convert GPS week/second to datetime object, and optionally store."""
    tow = sec_of_week
    second = int(tow)
    nanosecond = int((tow - second) * 1E9)
    return self._ReturnDateTime(
        xdatetime.datetime.from_gps_week_secs(week, second, nanosecond), store)

  def DatetimeFromTime(self, time):
    """Get timestamp as datetime object."""
    return self.last_dtime and xdatetime.datetime.from_datetime_time(
        self.last_dtime, time
        )
