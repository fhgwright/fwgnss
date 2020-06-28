"""Module for parsing Motorola Oncore NMEA and binary messages."""

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

# pylint: disable=too-many-lines

from __future__ import absolute_import, print_function, division

import operator

try:
  reduce
except NameError:
  from functools import reduce  # pylint: disable=redefined-builtin

from . import binary
from . import nmea


class Constants(nmea.Constants,  # pylint: disable=too-few-public-methods
                binary.Constants):
  """Class which holds various constant definitions."""


# Oncore NMEA additions

class NmeaParser(nmea.NmeaParser):
  """Class for Oncore NMEA parser (adds vendor sentences)."""
  NMEA_DICT = nmea.NmeaParser.NMEA_DICT

nmea.Sentence.PARSE_CLASS = NmeaParser


class NmeaDecoder(nmea.NmeaDecoder):
  """Oncore added NMEA sentence decoder."""
  DECODER_DICT = {}


# Oncore binary messages


class Message(binary.BinaryDataItem):
  """Generic Oncore binary message item from extracter."""
  # FIXME:  It seems that there is no form of byte stuffing in this format.
  # That means that the only way to avoid false CR-LF positives is to know
  # the expected (and fixed) message lengths for each message type.  This
  # is not currently implemented.
  ENDIANNESS = 'big'
  ENDIAN_PREFIX = binary.ENDIAN_PREFIXES[ENDIANNESS]

  HEADER = binary.MakeStruct(ENDIAN_PREFIX, ['2s 2s'])
  TRAILER = binary.MakeStruct(ENDIAN_PREFIX, ['B 2s'])
  HDR_SIZE = HEADER.size
  TRL_SIZE = TRAILER.size
  OVERHEAD = HDR_SIZE + TRL_SIZE
  SYNC = b'@@'
  END = b'\r\n'
  CKS_START = len(SYNC)
  END_LEN = len(END)
  TRL_OFS = -(TRL_SIZE - END_LEN)
  CKS_END = TRL_OFS
  HDR_REST = HDR_SIZE - CKS_START
  MIN_END = OVERHEAD - END_LEN

  LOG_PAT = 'Oncore-%s(%d)'
  SUMMARY_PAT = LOG_PAT
  SUMMARY_DESC_PAT = SUMMARY_PAT + ': %s'

  __slots__ = ()

  # Avoid pylint complaints for items we'll add later
  # pylint: disable=no-member

  @classmethod
  def Extract(cls, extracter):  # pylint: disable=too-many-return-statements
    """Extract an Oncore binary item from the input stream."""
    if not extracter.line.startswith(cls.SYNC):
      return None, 0
    _, msgtype = cls.HEADER.unpack_from(extracter.line)
    while True:
      endpos = extracter.line.find(cls.END)
      if endpos >= cls.MIN_END:
        break
      if len(extracter.line) > cls.LENGTH_LIMIT:
        return None, 0
      if not extracter.GetLine(cls.END_LEN):
        return None, 0
    checksum, _ = cls.TRAILER.unpack_from(extracter.line, endpos + cls.TRL_OFS)
    cbody = bytearray(extracter.line[cls.CKS_START:endpos+cls.CKS_END])
    body = cbody[cls.HDR_SIZE - cls.CKS_START:]
    actual_checksum = cls.Checksum(cbody)
    if actual_checksum != checksum:
      return None, 0
    length = len(body)
    if not isinstance(msgtype, str):
      msgtype = str(msgtype, encoding='ascii')
    item = cls.Make(data=body, length=length, msgtype=msgtype)
    return item, length + cls.OVERHEAD

  @staticmethod
  def Checksum(data):
    """Compute Oncore checksum of data supplied as bytes."""
    return reduce(operator.xor, bytearray(data), 0)

  def _GetLength(self):
    """Validate length and get full-message version."""
    # Documentation uses full lengths, so use it here as well.
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    return self.length + self.OVERHEAD

  def Contents(self):
    """Get full message content."""
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    checksum = self.Checksum(self.data)
    header = self.HEADER.pack(self.SYNC, self.msgtype)
    trailer = self.TRAILER.pack(*checksum)
    return b''.join([header, bytes(self.data), trailer])

  def Summary(self, full=False):
    """Get message summary text."""
    length = self._GetLength()
    parser = full and self.parser
    if parser:
      return self.SUMMARY_DESC_PAT % (self.msgtype, length, parser.DESCRIPTION)
    return self.SUMMARY_PAT % (self.msgtype, length)

  def LogText(self):
    """Get message text for logging."""
    length = self._GetLength()
    return self.LOG_PAT % (self.msgtype, length)


class BinaryExtracter(binary.Extracter):
  """Oncore binary message extracter."""

  def __new__(cls, infile=None):
    self = super(BinaryExtracter, cls).__new__(cls, infile)
    self.AddExtracter(Message, 3)
    self.parse_map['ONCORE'] = Message.PARSE_CLASS
    return self


# Need a global handle on this while defining the class
struct_dict = {}  # pylint: disable=invalid-name


def MakeParser(name, pattern):
  """Create a Oncore binary parser."""
  return binary.MakeParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


def DefineParser(name, pattern):
  """Define a Oncore binary parser."""
  binary.DefineParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


class BinaryParser(binary.Parser):
  """Oncore binary message parser."""
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
  """Oncore binary message decoder."""
  DECODER_DICT = {}


class Extracter(nmea.NmeaExtracter, BinaryExtracter):
  """Class for combined extracter."""


class Parser(NmeaParser, BinaryParser):
  """Class for combined parser."""


class Decoder(NmeaDecoder, BinaryDecoder):
  """Class for combined decoder."""
