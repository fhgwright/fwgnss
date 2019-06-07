"""GNSS-enhanced replacement (sort of) datetime module."""

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

from ..debuggable import Debuggable
from . import gps
from ..datetime import xdatetime


class Constants(Debuggable):  # pylint:disable=too-few-public-methods
  """Class which holds various constant definitions."""

  SECONDS_PER_DAY = xdatetime.SECONDS_PER_DAY
  NUM_WEEKDAYS = xdatetime.NUM_WEEKDAYS
  SECONDS_PER_WEEK = xdatetime.SECONDS_PER_WEEK

  GPS_BASE = xdatetime.DayNum(*gps.Constants.EPOCH)
  GPS_LEAP_OFFSET = xdatetime.LeapInfo(GPS_BASE)[0]


class date(xdatetime.date, Debuggable):  # pylint: disable=invalid-name
  """Date-only object, with ordinal and leap-second info."""


class time(xdatetime.time, Debuggable):  # pylint: disable=invalid-name
  """Time-only object."""


class datetime(xdatetime.datetime, Constants):  # pylint: disable=invalid-name
  """Date/time object."""

  @classmethod
  def from_gps_week_sec(cls,  # pylint: disable=invalid-name
                        week, second=0, nanosecond=0):
    """Create new datetime object from GPS week, second and nanosecond."""
    if week < 0:
      raise ValueError('Invalid week number')
    if second >= cls.SECONDS_PER_WEEK:
      raise ValueError('Bad second number')
    weekday, daysec = divmod(second + cls.GPS_LEAP_OFFSET, cls.SECONDS_PER_DAY)
    daynum = week * cls.NUM_WEEKDAYS + weekday
    days, seconds = xdatetime.TAIDaySecsToUTCDaySecs(daynum + cls.GPS_BASE,
                                                     daysec)
    year, month, day = xdatetime.DayNumToYMD(days)
    hour, minute, second = xdatetime.SecondsToHMS(seconds)
    return cls(year, month, day, hour, minute, second, nanosecond)

  def gps_week_sec_nano(self, roundofs=0):  # pylint: disable=invalid-name
    """Get GPS week, second, and nanosecond from datetime object."""
    days = self._days - self.GPS_BASE
    if days < 0:
      raise ValueError('Date precedes GPS origin')
    nanos = self.nanosecond + roundofs
    seconds = self.seconds + self.leapseconds - self.GPS_LEAP_OFFSET
    if nanos >= 1000000000:
      nanos -= 1000000000
      seconds += 1
    day_offset, seconds = divmod(seconds, self.SECONDS_PER_DAY)
    week, dow = divmod(days + day_offset, self.NUM_WEEKDAYS)
    return week, dow * self.SECONDS_PER_DAY + seconds, nanos
