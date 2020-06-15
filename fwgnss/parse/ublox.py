"""Module for parsing u-Blox NMEA and binary messages."""

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


# u-Blox NMEA additions

class NmeaParser(nmea.NmeaParser):
  """Class for u-Blox NMEA parser (adds vendor sentences)."""
  NMEA_DICT = nmea.NmeaParser.NMEA_DICT

nmea.Sentence.PARSE_CLASS = NmeaParser


class NmeaDecoder(nmea.NmeaDecoder):
  """u-Blox added NMEA sentence decoder."""
  DECODER_DICT = {}


# u-Blox binary messages


class Message(binary.BinaryDataItem):
  """Generic u-Blox binary message item from extracter."""
  ENDIANNESS = 'little'
  ENDIAN_PREFIX = binary.ENDIAN_PREFIXES[ENDIANNESS]

  HEADER = binary.MakeStruct(ENDIAN_PREFIX, ['2s B B H'])
  TRAILER = binary.MakeStruct(ENDIAN_PREFIX, ['2B'])
  HDR_SIZE = HEADER.size
  TRL_SIZE = TRAILER.size
  OVERHEAD = HDR_SIZE + TRL_SIZE
  SYNC = b'\xB5\x62'
  CKS_START = len(SYNC)
  HDR_REST = HDR_SIZE - CKS_START

  LOG_PAT = 'UBX-%02X-%02X(%d)'
  SUMMARY_PAT = LOG_PAT
  SUMMARY_DESC_PAT = SUMMARY_PAT + ': %s'

  __slots__ = ()

  @classmethod
  def Extract(cls, extracter):  # pylint: disable=too-many-return-statements
    """Extract a u-Blox binary item from the input stream."""
    if not extracter.line.startswith(cls.SYNC):
      return None, 0
    # Binary message may have embedded apparent EOLs
    while True:
      try:
        _, msgtype, subtype, length = (cls.HEADER.unpack_from(extracter.line))
      # Just in case header contains apparent EOL
      except binary.StructError:
        if not extracter.GetLine():
          return None, 0
        continue
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
    cbody = bytearray(extracter.line[cls.CKS_START:hlength])
    body = cbody[cls.HDR_REST:]
    checksum = cls.TRAILER.unpack_from(extracter.line, hlength)
    actual_checksum = cls.Checksum(cbody)
    if actual_checksum != checksum:
      return None, 0
    return cls.Make(data=body, length=length,
                    msgtype=msgtype, subtype=subtype), tlength

  @staticmethod
  def Checksum(data):
    """Fletcher checksum algorithm, with modulus=256."""
    ck_a = ck_b = 0
    for val in data:
      ck_a += val
      ck_b += ck_a
    return ck_a & 0xFF, ck_b & 0xFF

  def Contents(self):
    """Get full message content."""
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    checksum = self.Checksum(self.data)
    header = self.HEADER.pack(self.SYNC, self.msgtype, self.subtype,
                              self.length)
    trailer = self.TRAILER.pack(*checksum)
    return b''.join([header, bytes(self.data), trailer])

  def Summary(self, full=False):
    """Get message summary text."""
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    parser = full and self.parser
    if parser:
      return self.SUMMARY_DESC_PAT % (self.msgtype, self.subtype, self.length,
                                      parser.DESCRIPTION)
    return self.SUMMARY_PAT % (self.msgtype, self.subtype, self.length)

  def LogText(self):
    """Get message text for logging."""
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    return self.LOG_PAT % (self.msgtype, self.subtype, self.length)


class BinaryExtracter(binary.Extracter):
  """u-Blox binary message extracter."""

  def __new__(cls, infile=None):
    self = super(BinaryExtracter, cls).__new__(cls, infile)
    self.AddExtracter(Message, 10)
    self.parse_map['UBLOX'] = Message.PARSE_CLASS
    return self


# Need a global handle on this while defining the class
struct_dict = {}  # pylint: disable=invalid-name


def MakeParser(name, pattern):
  """Create a u-Blox binary parser."""
  return binary.MakeParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


def DefineParser(name, pattern):
  """Define a u-Blox binary parser."""
  binary.DefineParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


class BinaryParser(binary.Parser):
  """u-Blox binary message parser."""
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
  """u-Blox binary message decoder."""
  DECODER_DICT = {}


class Extracter(nmea.NmeaExtracter, BinaryExtracter):
  """Class for combined extracter."""


class Parser(NmeaParser, BinaryParser):
  """Class for combined parser."""


class Decoder(NmeaDecoder, BinaryDecoder):
  """Class for combined decoder."""
