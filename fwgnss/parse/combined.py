"""Combined GNSS parsing base, including all suported formats."""

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

from . import binary
from . import generic
from . import garmin
from . import hemisphere
from . import nmea
from . import oncore
from . import sirf
from . import ublox

# Convenience definitions

BinaryItem = binary.BinaryItem
ControlItem = generic.ControlItem
Sentence = nmea.Sentence


class Extracter(  # pylint: disable=too-many-ancestors
    nmea.Extracter,
    hemisphere.Extracter,
    sirf.Extracter,
    ublox.Extracter,
    oncore.Extracter,
    garmin.Extracter,
    ):
  """Combined Extracter class."""


class Parser(  # pylint: disable=too-many-ancestors
    nmea.Parser,
    hemisphere.Parser,
    sirf.Parser,
    ublox.Parser,
    oncore.Parser,
    garmin.Parser,
    ):
  """Combined Parser class."""


class Decoder(  # pylint: disable=too-many-ancestors
    nmea.Decoder,
    hemisphere.Decoder,
    sirf.Decoder,
    ublox.Decoder,
    oncore.Decoder,
    garmin.Decoder,
    ):
  """Combined Decoder class."""
