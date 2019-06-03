"""Module for basic generic GNSS definitions."""

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

from ..datadefs import Debuggable
from ..datetime import xdatetime


class Constants(Debuggable):  # pylint: disable=too-few-public-methods
  """Class which holds various constant definitions."""

  SECONDS_PER_DAY = xdatetime.SECONDS_PER_DAY
  SECONDS_PER_WEEK = xdatetime.SECONDS_PER_WEEK

  LIGHT_SPEED = 2.99792458E8  # In m/s

  # The GPS ICD specifies (albeit not entirely explicitly) a specific value
  # of PI to be used in certain calculations to ensure consistency.  In
  # particular, conversions from almanac/ephemeris orbital parameters to
  # positions are expected to use this value.
  # The Galileo ICD specifies something similar, with the same value.
  # It isn't known at this time whether GLONASS and/or Beidou are similar.
  GNSS_PI = 3.1415926535898
