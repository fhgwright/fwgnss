"""Module for parsing Garmin NMEA and binary messages."""

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


# Garmin NMEA additions

class NmeaParser(nmea.NmeaParser):
  """Class for Garmin NMEA parser (adds vendor sentences)."""
  NMEA_DICT = nmea.NmeaParser.NMEA_DICT

nmea.Sentence.PARSE_CLASS = NmeaParser


class NmeaDecoder(nmea.NmeaDecoder):
  """Garmin added NMEA sentence decoder."""
  DECODER_DICT = {}


# Garmin binary messages


class Message(binary.BinaryDataItem):
  """Generic Garmin binary message item from extracter."""
  ENDIANNESS = 'little'  # Specified somewhat obscurely in section 7.1
  ENDIAN_PREFIX = binary.ENDIAN_PREFIXES[ENDIANNESS]

  __slots__ = ()

  # Avoid pylint complaints for items we'll add later
  # pylint: disable=no-member

  @classmethod
  def Extract(cls, extracter):  # pylint: disable=too-many-return-statements
    """Extract a Garmin binary item from the input stream."""
    # Not implemented yet.
    _ = extracter
    return None, 0

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
      return self.SUMMARY_DESC_PAT % (self.msgtype, self.length,
                                      parser.DESCRIPTION)
    return self.SUMMARY_PAT % (self.msgtype, self.length)

  def LogText(self):
    """Get message text for logging."""
    if len(self.data) != self.length:
      raise binary.LengthError('%d != %d' % (len(self.data), self.length))
    return self.LOG_PAT % (self.msgtype, self.length)


class BinaryExtracter(binary.Extracter):
  """Garmin binary message extracter."""

  def __new__(cls, infile=None):
    self = super(BinaryExtracter, cls).__new__(cls, infile)
    self.AddExtracter(Message, 3)
    self.parse_map['GARMIN'] = Message.PARSE_CLASS
    return self


# Need a global handle on this while defining the class
struct_dict = {}  # pylint: disable=invalid-name


def MakeParser(name, pattern):
  """Create a Garmin binary parser."""
  return binary.MakeParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


def DefineParser(name, pattern):
  """Define a Garmin binary parser."""
  binary.DefineParser(name, Message.ENDIAN_PREFIX, struct_dict, pattern)


class BinaryParser(binary.Parser):
  """Garmin binary message parser."""
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
  """Garmin binary message decoder."""
  DECODER_DICT = {}


class Extracter(nmea.NmeaExtracter, BinaryExtracter):
  """Class for combined extracter."""


class Parser(NmeaParser, BinaryParser):
  """Class for combined parser."""


class Decoder(NmeaDecoder, BinaryDecoder):
  """Class for combined decoder."""
