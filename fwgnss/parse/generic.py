"""Generic GNSS parsing base."""

#                      Copyright (c) 2022
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

import collections
from operator import itemgetter
import sys

from ..datadefs import BindDictFuncs
from ..debuggable import Debuggable
from ..systems import generic
from ..systems import glonass
from ..systems import gps
from ..systems import xdatetime


class Error(Exception):
  """Base class for all exceptions defined in parser modules."""


class Constants(Debuggable):  # pylint:disable=too-few-public-methods
  """Class which holds various constant definitions."""

  SECONDS_PER_DAY = generic.Constants.SECONDS_PER_DAY
  SECONDS_PER_WEEK = generic.Constants.SECONDS_PER_WEEK
  GPS_LEAPS = xdatetime.Constants.GPS_LEAP_OFFSET

  # System ID codes (NMEA and internal)
  SYSTEM_ID_GPS = 1
  SYSTEM_ID_GLONASS = 2
  SYSTEM_ID_GALILEO = 3
  SYSTEM_ID_BEIDOU = 4  # From u-blox, may not be officially NMEA
  SYSTEM_DECODE = {1: 'GPS', 2: 'GLONASS', 3: 'Galileo', 4: 'BeiDou'}

  # Satellite type codes (internal)
  SAT_TYPE_GPS = 0
  SAT_TYPE_SBAS = 1
  SAT_TYPE_GLONASS = 2
  SAT_TYPE_GALILEO = 3
  SAT_TYPE_BEIDOU = 4
  SAT_TYPE_QZSS = 5
  SAT_TYPE_IRNSS = 6
  SAT_TYPE_IMES = 7
  # Type letters from RINEX (except IMES)
  SAT_TYPE_LETTERS = ('G', 'S', 'R', 'E', 'C', 'J', 'I', 'x')

  # Signal type codes (internal)
  SIGNAL_L1CA = 0
  SIGNAL_L1P = 1
  SIGNAL_L2P = 2
  SIGNAL_G1 = 3
  SIGNAL_G2 = 4
  SIGNAL_NAMES = ('L1 C/A', 'L1P', 'L2P', 'G1', 'G2')

  # Wavelengths by signal type
  GPS_L1_WAVELENGTH = gps.Constants.L1_WAVELENGTH
  GPS_L2_WAVELENGTH = gps.Constants.L2_WAVELENGTH
  GLO_L1_WAVELENGTHS = glonass.Constants.L1_WAVELENGTHS
  GLO_L2_WAVELENGTHS = glonass.Constants.L2_WAVELENGTHS
  SIGNAL_WAVELENGTH = (
      GPS_L1_WAVELENGTH,
      GPS_L1_WAVELENGTH,
      GPS_L2_WAVELENGTH,
      None,  # Knum-dependent
      None,  # Knum-dependent
      )


class BaseItem(Debuggable):  # pylint:disable=too-many-instance-attributes
  """Base class for extracted items."""
  PARSE_CLASS = None

  __slots__ = ('data', 'length', 'msgtype', 'subtype',
               'parser', 'parsed', 'parse_error',
               'decoded', 'decode_error', 'charpos')

  def __init__(self, data=None, length=None, msgtype=None, subtype=None):
    self.data = data
    self.length = length or len(data)
    self.msgtype = msgtype
    self.subtype = subtype
    self.parser = None
    self.parsed = None
    self.parse_error = None
    self.decoded = None
    self.decode_error = None
    self.charpos = None

  @staticmethod
  def Contents():
    """Return full contents of item."""
    return None

  @staticmethod
  def Summary(full=False):
    """Return summary text for item."""
    _ = full

  def LogText(self):
    """Return item text for logging."""
    return self.Summary()

  @classmethod
  def Make(cls, *args, **kwargs):
    """Create a new instance of this item type."""
    # Overridable if type is data-dependent.
    return cls(*args, **kwargs)


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

  IS_BINARY = False

  __slots__ = ()


class ControlItem(Item):
  """Base class for extracted control items."""
  __slots__ = ()


class TextControlItem(ControlItem, TextItem):
  """Base class for text-based extracted control items."""
  __slots__ = ()


class Comment(TextItem):
  """Class for comment lines."""
  PREFIX_IN = b'#'
  MAX_LENGTH = 132
  BAD_CHARS = set(range(ord(' '))) - set([ord('\t')])

  __slots__ = ()

  @classmethod
  def Extract(cls, extracter):
    """Extracter for comment lines."""
    if  not extracter.line.startswith(cls.PREFIX_IN):
      return None, 0
    length, endlen = extracter.GetEOL()
    if not endlen or length > cls.MAX_LENGTH:
      return None, 0
    data = extracter.GetText(extracter.line[:length])
    if data is None:
      return None, 0
    for char in bytearray(data, encoding=cls.TEXT_ENCODING):
      if char in cls.BAD_CHARS:
        return None, 0
    return cls.Make(data=data, length=length), length + endlen

  def Contents(self):
    return self.data

  def Summary(self, full=False):
    return self.data

  def LogText(self):
    return self.data


class Extracter(Debuggable):  # pylint: disable=too-many-instance-attributes
  """Base class for extracters."""
  LINE_MAX = 500  # Generous limit - just defends against non-CRLF data

  # Dummy defs to placate pylint, overridden in subclasses
  ENDIANNESS = None

  def __new__(cls, infile=None):
    _ = infile
    self = super(Extracter, cls).__new__(cls)
    self.extractables = []
    self.extracters = []
    self.parse_map = {}
    return self

  def __init__(self, infile=None):
    self.input = infile
    self.line = b''
    self.charpos = 0
    self.linenum = 0       # For debugging
    self.linebreak = 0     # To stop on line for debugging
    self.skipped = b''     # Unrecognized data we skipped
    self.extended = False  # True if we needed to extend line to get an item
    self.extractables = self.extractables  # Placate pylint 3
    self.parse_map = self.parse_map            # Ditto
    self.BindExtracters()

  def AddExtracter(self, cls, prio=0):
    """Add a new extracter item class to list, with priority."""
    for num, ent in enumerate(self.extractables):
      # Filter out duplicates
      if ent[1] == cls:
        return
      # Filter out overridden methods from parent classes
      if isinstance(cls, ent[0]):
        self.extractables.pop(num)
        break
    # Initially, we reverse the order to compensate for the reversed order
    # in the calls from __init__().  After the initial BindExtracters()
    # call, subsequent additions are at the end.
    if self.extracters:
      self.extractables.append((cls, prio))
    else:
      self.extractables.insert(0, (cls, prio))

  def BindExtracters(self):
    """Derive a list of bound extracter methods from extractables."""
    # Sort by descending priorities
    extractables = sorted(self.extractables, key=itemgetter(1), reverse=True)
    self.extracters = [x[0].Extract for x in extractables]

  def MergeExtracters(self, other):
    """Merge list of extracters from other extracter into this one."""
    if not isinstance(other, Extracter):
      types = (type(other), Extracter)
      raise TypeError('Type mismatch: %s not instance of %s' % types)
    for cls, prio in other.extractables:
      self.AddExtracter(cls, prio)
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
    item = ErrorItem.Make(self.skipped)
    self.skipped = b''
    item.charpos = self.charpos
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
        item, consumed = extracter(self)
        if item:
          break
      if item:
        if self.skipped:
          yield self._GetErrorItem()
        item.charpos = self.charpos
        yield item
        self.line = self.line[consumed:]
        self.charpos += consumed
        continue
      if self.line:
        self.skipped += self.line[:1]
        self.line = self.line[1:]
        self.charpos += 1
        continue
      if self.skipped:
        yield self._GetErrorItem()

  @staticmethod
  def GetText(data):
    """Convert data from bytes to string, if needed."""
    # Always runs decode to check for non-ASCII characters
    # Wraps with str() to ensure str rather than unicode in Python 2
    try:
      return str(data.decode(TextItem.TEXT_ENCODING))
    except UnicodeDecodeError:
      pass
    return None

  def AllowComments(self):
    """Enable comment-line recognition in this Extracter."""
    self.MergeExtracters(CommentExtracter())


class CommentExtracter(Extracter):
  """Class for comment-line extracter."""
  def __new__(cls, infile=None):
    self = super(CommentExtracter, cls).__new__(cls, infile)
    self.AddExtracter(Comment)
    return self


class Parser(Debuggable):
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

  class ParseItem(Debuggable):  # pylint: disable=too-few-public-methods
    """Base class for type-specific parsers."""

    @classmethod
    def ThisParser(cls, subtype=None):
      """Obtain subtype-specific parser for this item."""
      _ = subtype
      return cls


class Decoder(Debuggable):
  """Base class for item decoders."""

  def __init__(self):
    self.last_time = None
    self.last_dtime = None
    self.decoder_dict = BindDictFuncs('DECODER_DICT', self)

  SatResidual = collections.namedtuple('Residual', 'sat type num value')
  SatView = collections.namedtuple('SatView', 'sat type num')

  def Decode(self, item, ignore_error=False):
    """Return and store the decoded version of this item."""
    decoder = self.decoder_dict.get(item.parser)
    # If not found, try parent classes
    if not decoder:
      for parser in item.parser.__mro__:
        decoder = self.decoder_dict.get(parser)
        if decoder:
          break
    if decoder:
      if ignore_error:
        try:
          decoded = decoder(item)
        # Any exception aborts decode
        except:  # pylint: disable=bare-except
          decoded = None
      else:
        decoded = decoder(item)
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
    nano = int((tow - second) * 1E9)
    return self._ReturnDateTime(
        xdatetime.datetime.from_gps_week_sec(week, second, nano), store)

  def DatetimeFromTime(self, time):
    """Get timestamp as datetime object."""
    return self.last_dtime and xdatetime.datetime.from_datetime_time(
        self.last_dtime, time
        )
