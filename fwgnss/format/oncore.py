"""Module for formatting Motorola Oncore data into human-friendly form."""

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

from . import generic
from . import nmea
from ..parse import oncore

VENDORS = set(['Oncore'])


class NmeaConstants(nmea.Constants):  # pylint: disable=too-few-public-methods
  """Class for various NMEA-related constant definitions."""


class NmeaFormatter(nmea.NmeaFormatter):
  """Class for Oncore NMEA formatter objects."""
  PARSER = oncore.NmeaParser
  DECODER = oncore.NmeaDecoder

  FORMATTER_DICT = {}


class OncoreConstants(oncore.Constants):  # pylint: disable=too-few-public-methods
  """Class for various Oncore-related constant definitions."""


class BinaryFormatter(generic.BinaryFormatter):
  """Class for Oncore binary formatter objects."""
  EXTRACTER = oncore.BinaryExtracter
  PARSER = oncore.BinaryParser
  DECODER = oncore.BinaryDecoder

  FORMATTER_DICT = {}


class Formatter(NmeaFormatter, BinaryFormatter):
  """Class for combined formatter."""
  EXTRACTER = oncore.Extracter
  PARSER = oncore.Parser
  DECODER = oncore.Decoder
