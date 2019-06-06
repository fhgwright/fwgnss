"""Module for parsing SiRF NMEA and binary messages."""

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

# pylint: disable=too-many-lines

from __future__ import absolute_import, print_function, division

from . import binary
from . import nmea


class Constants(nmea.Constants,  # pylint: disable=too-few-public-methods
                binary.Constants):
  """Class which holds various constant definitions."""


# SiRF NMEA additions

class NmeaParser(nmea.NmeaParser):
  """Class for SiRF NMEA parser (adds vendor sentences)."""
  NMEA_DICT = nmea.NmeaParser.NMEA_DICT

nmea.Sentence.PARSE_CLASS = NmeaParser


class NmeaDecoder(nmea.NmeaDecoder):
  """SiRF added NMEA sentence decoder."""
  DECODER_DICT = {}


# SiRF binary messages


class Message(binary.BinaryDataItem):
  """Generic SiRF binary message item from extracter."""
  ENDIANNESS = 'big'
  ENDIAN_PREFIX = binary.ENDIAN_PREFIXES[ENDIANNESS]

  HEADER = binary.MakeStruct(ENDIAN_PREFIX, ['2s H'])
  TRAILER = binary.MakeStruct(ENDIAN_PREFIX, ['H 2s'])
  HDR_SIZE = HEADER.size
  TRL_SIZE = TRAILER.size
  OVERHEAD = HDR_SIZE + TRL_SIZE
  SYNC = b'\xA0\xA2'
  END = b'\xB0\xB3'

  LOG_PAT = 'SiRF-%02X(%d)'
  SUMMARY_PAT = LOG_PAT
  SUMMARY_DESC_PAT = SUMMARY_PAT + ': %s'

  __slots__ = ()

  @classmethod
  def Extract(cls, extracter):  # pylint: disable=too-many-return-statements
    """Extract a SiRF binary item from the input stream."""
    if not extracter.line.startswith(cls.SYNC):
      return None, 0
    # Binary message may have embedded apparent EOLs
    while True:
      try:
        _, length = cls.HEADER.unpack(extracter.line[:cls.HDR_SIZE])
      # Just in case header contains apparent EOL
      except binary.StructError:
        if not extracter.GetLine():
          return None, 0
        continue
      # Enforcing the 15-bit length limit is implicit in the limit check
      if length > cls.LENGTH_LIMIT:
        return None, 0
      needed = length + cls.OVERHEAD - len(extracter.line)
      if needed > 0:
        if not extracter.GetLine(needed):
          return None, 0
        continue
      break
    hlength = cls.HDR_SIZE + length
    tlength = hlength + cls.TRL_SIZE
    body = bytearray(extracter.line[cls.HDR_SIZE:hlength])
    checksum, end = cls.TRAILER.unpack(extracter.line[hlength:tlength])
    actual_checksum = cls.Checksum(body)
    if actual_checksum != checksum or end != cls.END:
      return None, 0
    return cls.Make(data=body, length=length, msgtype=body[0]), tlength

  @staticmethod
  def Checksum(data):
    """Compute checksum of data."""
    # The SiRF checksum is just a simple sum, masked to 15 bits.
    return sum(data) & 0x7FFF

  def Contents(self):
    """Get full message content."""
    if len(self.data) != self.length:
      raise ValueError
    checksum = self.Checksum(self.data)
    header = self.HEADER.pack(self.SYNC, self.length)
    trailer = self.TRAILER.pack(checksum, self.END)
    return b''.join([header, bytes(self.data), trailer])

  def Summary(self, full=False):
    """Get message summary text."""
    if len(self.data) != self.length:
      raise ValueError
    parser = full and self.parser
    if parser:
      return self.SUMMARY_DESC_PAT % (self.msgtype, self.length,
                                      parser.DESCRIPTION)
    return self.SUMMARY_PAT % (self.msgtype, self.length)

  def LogText(self):
    """Get message text for logging."""
    if len(self.data) != self.length:
      raise ValueError
    return self.LOG_PAT % (self.msgtype, self.length)


class BinaryExtracter(binary.Extracter):
  """SiRF binary message extracter."""

  def __new__(cls, infile=None):
    self = super(BinaryExtracter, cls).__new__(cls, infile)
    self.AddExtracter(BinaryExtracter, 'ExtractSirf', 5)
    self.parse_map['SIRF'] = Message.PARSE_CLASS
    return self

  def ExtractSirf(self):  # pylint: disable=too-many-return-statements
    """Extract a SiRF binary item from the input stream."""
    return Message.Extract(self)


# Need a global handle on this while defining the class
struct_dict = {}  # pylint: disable=invalid-name


def MakeParser(name, pattern):
  """Create a SiRF binary parser."""
  return binary.MakeParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


def DefineParser(name, pattern):
  """Define a SiRF binary parser."""
  binary.DefineParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


class BinaryParser(binary.Parser):
  """SiRF binary message parser."""
  MESSAGE_DICT = {}
  STRUCT_DICT = struct_dict

  # pylint: disable=too-few-public-methods

  @classmethod
  def GetParser(cls, msgtype, subtype=None):
    return cls.MESSAGE_DICT.get(msgtype)

  class MessageParser(binary.Parser.MessageParser):
    """Base class for message-specific parsers."""

Message.PARSE_CLASS = BinaryParser

del struct_dict


class BinaryDecoder(binary.Decoder):
  """SiRF binary message decoder."""
  DECODER_DICT = {}


class Extracter(nmea.NmeaExtracter, BinaryExtracter):
  """Class for combined extracter."""


class Parser(NmeaParser, BinaryParser):
  """Class for combined parser."""


class Decoder(NmeaDecoder, BinaryDecoder):
  """Class for combined decoder."""
