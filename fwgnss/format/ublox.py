"""Module for formatting u-Blox data into human-friendly form."""

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

from . import generic
from . import nmea
from ..parse import ublox

VENDORS = set(['u-Blox'])


class NmeaConstants(nmea.Constants):  # pylint: disable=too-few-public-methods
  """Class for various NMEA-related constant definitions."""


class NmeaFormatter(nmea.NmeaFormatter):
  """Class for u-Blox NMEA formatter objects."""
  PARSER = ublox.NmeaParser
  DECODER = ublox.NmeaDecoder

  FORMATTER_DICT = {}


class UbloxConstants(ublox.Constants):  # pylint: disable=too-few-public-methods
  """Class for various u-Blox-related constant definitions."""


class BinaryFormatter(generic.BinaryFormatter):
  """Class for u-Blox binary formatter objects."""
  EXTRACTER = ublox.BinaryExtracter
  PARSER = ublox.BinaryParser
  DECODER = ublox.BinaryDecoder

  FORMATTER_DICT = {}


class Formatter(NmeaFormatter, BinaryFormatter):
  """Class for combined formatter."""
  EXTRACTER = ublox.Extracter
  PARSER = ublox.Parser
  DECODER = ublox.Decoder
