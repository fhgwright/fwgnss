"""Module for basic generic GNSS parameters and functions."""

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

SECONDS_PER_DAY = 24 * 60 * 60
SECONDS_PER_WEEK = SECONDS_PER_DAY * 7

LIGHT_SPEED = 2.99792458E8  # m/s
GPS_PI = 3.1415926535898  # Value of PI specified for all GPS calculations

GPS_BASE_FREQUENCY = 10.23E6  # Hz

GPS_L1_FREQUENCY = GPS_BASE_FREQUENCY * 154
GPS_L1_WAVELENGTH = LIGHT_SPEED / GPS_L1_FREQUENCY

GPS_L2_FREQUENCY = GPS_BASE_FREQUENCY * 120
GPS_L2_WAVELENGTH = LIGHT_SPEED / GPS_L2_FREQUENCY

GPS_L5_FREQUENCY = GPS_BASE_FREQUENCY * 115
GPS_L5_WAVELENGTH = LIGHT_SPEED / GPS_L5_FREQUENCY

GLO_L1_BASE_FREQUENCY = 1602.0E6
GLO_L1_K_MULTIPLIER = 0.5625E6

GLO_L2_BASE_FREQUENCY = 1246.0E6
GLO_L2_K_MULTIPLIER = 0.4375E6

GLO_L3_BASE_FREQUENCY = 1204.704E6
GLO_L3_K_MULTIPLIER = 0.423E6

GLO_MIN_K = -7
GLO_MAX_K = +6

def GlonassFrequencies(base, mult):
  """Get list mapping GLONASS K number to frequency."""
  return [(k, base + k * mult) for k in range(GLO_MIN_K, GLO_MAX_K + 1)]

def GlonassWavelengths(freqs):
  """Get list mapping GLONASS K number to wavelength."""
  return [(k, LIGHT_SPEED / freqs[k]) for k in range(GLO_MIN_K, GLO_MAX_K + 1)]

GLO_L1_FREQUENCIES = dict(GlonassFrequencies(GLO_L1_BASE_FREQUENCY,
                                             GLO_L1_K_MULTIPLIER))
GLO_L1_WAVELENGTHS = dict(GlonassWavelengths(GLO_L1_FREQUENCIES))

GLO_L2_FREQUENCIES = dict(GlonassFrequencies(GLO_L2_BASE_FREQUENCY,
                                             GLO_L2_K_MULTIPLIER))
GLO_L2_WAVELENGTHS = dict(GlonassWavelengths(GLO_L2_FREQUENCIES))

# The L3 part may or may not be correct.

GLO_L3_FREQUENCIES = dict(GlonassFrequencies(GLO_L3_BASE_FREQUENCY,
                                             GLO_L3_K_MULTIPLIER))
GLO_L3_WAVELENGTHS = dict(GlonassWavelengths(GLO_L2_FREQUENCIES))
