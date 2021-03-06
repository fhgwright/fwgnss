"""Module for basic GPS definitions."""

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


class Constants(generic.Constants):  # pylint: disable=too-few-public-methods
  """Class which holds various constant definitions."""

  BASE_FREQUENCY = 10.23E6  # Hz

  L1_FREQUENCY = BASE_FREQUENCY * 154
  L1_WAVELENGTH = generic.Constants.LIGHT_SPEED / L1_FREQUENCY

  L2_FREQUENCY = BASE_FREQUENCY * 120
  L2_WAVELENGTH = generic.Constants.LIGHT_SPEED / L2_FREQUENCY

  L5_FREQUENCY = BASE_FREQUENCY * 115
  L5_WAVELENGTH = generic.Constants.LIGHT_SPEED / L5_FREQUENCY

  EPOCH = (1980, 1, 6)  # Origin of GPS timescale
