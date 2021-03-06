"""Combined module for formatting of all supported GNSS data formats."""

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

from ..parse import combined
from . import garmin
from . import hemisphere
from . import nmea
from . import oncore
from . import sirf
from . import ublox


class Formatter(  # pylint: disable=too-many-ancestors
    nmea.Formatter,
    hemisphere.Formatter,
    sirf.Formatter,
    ublox.Formatter,
    oncore.Formatter,
    garmin.Formatter,
    ):
  """Combined Formatter class."""
  EXTRACTER = combined.Extracter
  PARSER = combined.Parser
  DECODER = combined.Decoder
