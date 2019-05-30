"""Module for basic GLONASS definitions."""

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


def _Frequencies(base, mult, k_range):
  """Get list mapping K number to frequency."""
  return [(k, base + k * mult) for k in k_range]


def _Wavelengths(freqs, k_range):
  """Get list mapping GLONASS K number to wavelength."""
  return [(k, generic.Constants.LIGHT_SPEED / freqs[k]) for k in k_range]


class Constants(generic.Constants):  # pylint: disable=too-few-public-methods
  """Class which holds various constant definitions."""

  L1_BASE_FREQUENCY = 1602.0E6
  L1_K_MULTIPLIER = 0.5625E6

  L2_BASE_FREQUENCY = 1246.0E6
  L2_K_MULTIPLIER = 0.4375E6

  L3_BASE_FREQUENCY = 1204.704E6
  L3_K_MULTIPLIER = 0.423E6

  MIN_K = -7
  MAX_K = +6

  K_RANGE = range(MIN_K, MAX_K + 1)

  L1_FREQUENCIES = dict(_Frequencies(L1_BASE_FREQUENCY, L1_K_MULTIPLIER,
                                     K_RANGE))
  L1_WAVELENGTHS = dict(_Wavelengths(L1_FREQUENCIES, K_RANGE))

  L2_FREQUENCIES = dict(_Frequencies(L2_BASE_FREQUENCY, L2_K_MULTIPLIER,
                                     K_RANGE))
  L2_WAVELENGTHS = dict(_Wavelengths(L2_FREQUENCIES, K_RANGE))

  # The L3 part may or may not be correct.

  L3_FREQUENCIES = dict(_Frequencies(L3_BASE_FREQUENCY, L3_K_MULTIPLIER,
                                     K_RANGE))
  L3_WAVELENGTHS = dict(_Wavelengths(L3_FREQUENCIES, K_RANGE))
