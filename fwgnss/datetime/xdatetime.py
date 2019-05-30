"""Replacement (sort of) datetime module."""

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

# Since neither time nor datetime handle leap seconds correctly, we roll our own
# date/time support here.
#
# While we're at it, we improve the resolution to nanoseconds.
#
# Dates are internally kept as ordinal day numbers, ignoring the "Gregorian
# glitch", which isn't currently handled.  I.e., dates prior to 15-Oct-1582
# aren't handled correctly.
#
# Times are kept as seconds/nanoseconds, and date/times combine these with
# day numbers.  This format avoids rollover issues in the plausible future,
# and also allows leap seconds to be uniquely represented.  The values
# are UTC-based, but carry leap offsets to allow TAI conversions.

import time as _time

from . import leapseconds

try:
  cmp
except NameError:
  def cmp(a, b):  # pylint: disable=redefined-builtin,invalid-name
    """Reinstate cmp from Python 2."""
    return (a > b) - (a < b)

_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
NUM_MONTHS = 12
_LEAP_MONTH = 2
NUM_WEEKDAYS = 7
SECONDS_PER_DAY = 24 * 60 * 60  # In the absence of leap seconds
SECONDS_PER_WEEK = NUM_WEEKDAYS * SECONDS_PER_DAY

_MAX_SECONDS = 70  # Allow for worst-case leap seconds at end of 1971

_MONTH_NAMES = (
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
    )
_MONTH_ABBR = tuple([x[:3] for x in _MONTH_NAMES])
_MONTH_DICT = dict([(n, v) for v, n in enumerate(_MONTH_NAMES, 1)]
                   + [(n, v) for v, n in enumerate(_MONTH_ABBR, 1)])

# Weekday names in Python (Monday as 0) order
_WEEKDAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday')
_WEEKDAY_ABBR_3 = tuple([x[:3] for x in _WEEKDAY_NAMES])
_WEEKDAY_ABBR_2 = tuple([x[:2] for x in _WEEKDAY_NAMES])
_WEEKDAY_DICT = dict(
    [(n, v) for v, n in enumerate(_WEEKDAY_NAMES)]
    + [(n, v) for v, n in enumerate(_WEEKDAY_ABBR_3)]
    + [(n, v) for v, n in enumerate(_WEEKDAY_ABBR_2)]
    )

_YEAR_DAYS = 365


def MonthNum(name):
  """Map month names (full or 3-letter) to month numbers."""
  return _MONTH_DICT.get(name.capitalize(), 0)


def MonthName(num, length=99):
  """Get month name for given month number, with length limit."""
  if num < 1 or num > NUM_MONTHS:
    raise ValueError('Bad month number')
  return _MONTH_NAMES[num - 1][:length]


def WeekdayNum(name):
  """Map weekday names (full, 2-, or 3-letter) to weekday numbers."""
  return _WEEKDAY_DICT.get(name.capitalize(), 0)


def WeekdayName(num, length=99):
  """Get weekday name for given weekday number, with length limit."""
  if num < 1 or num > NUM_WEEKDAYS:
    raise ValueError('Bad weekday number')
  return _WEEKDAY_NAMES[num][:length]


# Date operations treat the year as starting on 01-March, to place the leap
# day at the end.

# pylint: disable=invalid-name

_day_offset = 0

_post_leap_offsets = []
_post_leap_reverse = []
_month = _LEAP_MONTH + 1
for _count in _DAYS_IN_MONTH[_LEAP_MONTH:]:
  _post_leap_offsets.append((_count, 0, _day_offset))
  for _num in range(_count):
    _post_leap_reverse.append((0, _month, _day_offset))
  _day_offset += _count
  _month += 1
_post_offset = _day_offset

_pre_leap_offsets = []
_pre_leap_reverse = []
_month = 1
for _count in _DAYS_IN_MONTH[:_LEAP_MONTH]:
  _pre_leap_offsets.append((_count, -1, _day_offset))
  for _num in range(_count):
    _pre_leap_reverse.append((1, _month, _day_offset))
  _day_offset += _count
  _month += 1
_pre_leap_reverse.append((1, _LEAP_MONTH, _day_offset - _count))  # For leap day

_YEAR_DAY_OFFSETS = tuple(_pre_leap_offsets + _post_leap_offsets)
_REVERSE_OFFSETS = tuple(_post_leap_reverse + _pre_leap_reverse)
_PRE_LEAP_OFFSET = _day_offset - _post_offset
del _day_offset, _month, _count, _num, _post_offset
del _pre_leap_offsets, _post_leap_offsets, _pre_leap_reverse, _post_leap_reverse

# pylint: enable=invalid-name


def _DayNum(year, month, day):
  """Compute day number from date, where 0 = 01-Jan-0000."""
  if month < 1 or month > NUM_MONTHS:
    raise ValueError('Bad month number')
  month_days, year_offset, day_offset = _YEAR_DAY_OFFSETS[month - 1]
  if (month == _LEAP_MONTH
      and year % 4 == 0
      and (not year % 100 == 0 or (year % 400 == 0 and not year % 4000 == 0))):
    month_days += 1
  if day < 1 or day > month_days:
    raise ValueError('Bad day number')
  adj_year = year + year_offset
  num_leaps = (adj_year // 4 - adj_year // 100 + adj_year // 400
               - adj_year // 4000)
  year_day = adj_year * _YEAR_DAYS + num_leaps
  return year_day + day - 1 + day_offset + _PRE_LEAP_OFFSET


# Generate reverse chronological map from day numbers to cumulative leap
# second counts.

# pylint: disable=invalid-name

_rev_leap = leapseconds.TABLE[::-1] + [(1970, 1, 1, 0)]
_leap_list = [(_DayNum(*x[:3]), x[3]) for x in _rev_leap]
_LEAP_TABLE = tuple(zip(*_leap_list))
del _rev_leap, _leap_list

# pylint: enable=invalid-name


def _LeapInfo(daynum):
  """Return total leap seconds at start of day, and total seconds in day."""
  nextday = daynum + 1
  index = 0
  # _LEAP_TABLE is guaranteed nonempty, so 'start' is guaranteed initialized.
  for start in _LEAP_TABLE[0]:
    if nextday >= start:
      break
    index += 1
  else:
    return 0, SECONDS_PER_DAY
  num_leaps = _LEAP_TABLE[1][index]
  leap_change = 0
  if nextday == start:  # pylint: disable=undefined-loop-variable
    leap_change = num_leaps - _LEAP_TABLE[1][index + 1]
  return num_leaps - leap_change, SECONDS_PER_DAY + leap_change

_GREGORIAN_SKIP_START = _DayNum(1582, MonthNum('Oct'), 4)
_GREGORIAN_SKIP_END = _DayNum(1582, MonthNum('Oct'), 15)
_TAI_BASE = _DayNum(1958, MonthNum('Jan'), 1)
_MJD_BASE = _DayNum(1858, MonthNum('Nov'), 17)
_UNIX_BASE = _DayNum(1970, MonthNum('Jan'), 1)

_GPS_BASE = _DayNum(1980, MonthNum('Jan'), 6)
GPS_LEAP_OFFSET = _LeapInfo(_GPS_BASE)[0]

FMT_ISO8601 = '%Y-%m-%dT%H:%M:%S'


def DayNumMJD(year, month, day):
  """Get day number relative to MJD base."""
  return _DayNum(year, month, day) - _MJD_BASE


def DayNumUnix(year, month, day):
  """Get day number relative to Unix base."""
  return _DayNum(year, month, day) - _UNIX_BASE


_CYCLE_BASE = _DayNum(0, _LEAP_MONTH + 1, 1)

def _DayCount(num_years):
  return _DayNum(num_years, _LEAP_MONTH + 1, 1) - _CYCLE_BASE


_QUADYEAR_DAYS = _DayCount(4)
_CENTURY_DAYS = _DayCount(100)
_QUADRICENTURY_DAYS = _DayCount(400)
_QUADRIMILLENIUM_DAYS = _DayCount(4000)

_QUADRIMILLENIUM_BASE = _DayNum(4000, 1, 1)


def _DayNumToYMD(daynum):
  if daynum < _GREGORIAN_SKIP_END:
    raise ValueError('Date too early')
  qmill, qmilld = divmod(daynum - _CYCLE_BASE, _QUADRIMILLENIUM_DAYS)
  qcent, qcentd = divmod(qmilld, _QUADRICENTURY_DAYS)
  cent, centd = divmod(qcentd, _CENTURY_DAYS)
  if cent == 4:
    cent -= 1
    centd += _CENTURY_DAYS
  qyear, qyeard = divmod(centd, _QUADYEAR_DAYS)
  year, yeard = divmod(qyeard, _YEAR_DAYS)
  if year == 4:
    year -= 1
    yeard += _YEAR_DAYS
  rel_year = qmill * 4000 + qcent * 400 + cent * 100 + qyear * 4 + year
  year_offset, month, day_offset = _REVERSE_OFFSETS[yeard]
  return rel_year + year_offset, month, yeard - day_offset + 1

_WEEKDAY_BASE = (WeekdayNum('Wed') - _MJD_BASE) % NUM_WEEKDAYS


def _DayNumToWeekdayNum(daynum):
  return (daynum + _WEEKDAY_BASE) % NUM_WEEKDAYS


def _SecondsNanos(hour, minute, second, nanosecond=0):
  if hour >= 24 or minute >= 60 or second >= _MAX_SECONDS:
    raise ValueError('Bad time component')
  if nanosecond >= 1000000000:
    raise ValueError('Bad nanosecond value')
  return ((hour * 60) + minute) * 60 + second, nanosecond


def _SecondsToHMS(seconds, leapok=True):
  leaps = (leapok and seconds >= SECONDS_PER_DAY
           and seconds - SECONDS_PER_DAY + 1) or 0
  minutes, second = divmod(seconds - leaps, 60)
  hour, minute = divmod(minutes, 60)
  return hour, minute, second + leaps


def _TAIDaySecsToUTCDaySecs(day, second):
  leap_seconds, num_seconds = _LeapInfo(day)
  while second < leap_seconds:
    day -= 1
    second += num_seconds
    leap_seconds, num_seconds = _LeapInfo(day)
  return day, second - leap_seconds


def LocalStrftime(fmt, struct, microstr):
  """Version of strftime with subsecond support."""
  fmt = fmt.replace('%f', microstr)
  return _time.strftime(fmt, struct)


class date(object):  # pylint: disable=invalid-name
  """Date-only object, with ordinal and leap-second info."""
  def __new__(cls, year, month=1, day=1):
    days = _DayNum(year, month, day)
    if days < _GREGORIAN_SKIP_END:
      raise ValueError('Date too early')
    leap_seconds, num_seconds = _LeapInfo(days)
    self = object.__new__(cls)
    # pylint: disable=protected-access
    self._days = days
    self.year, self.month, self.day = year, month, day
    self.leapseconds, self.num_seconds = leap_seconds, num_seconds
    self._struct = None
    return self

  @classmethod
  def from_daynum(cls, daynum):  # pylint: disable=invalid-name
    """Create new date object from absolute day number."""
    year, month, day = _DayNumToYMD(daynum)
    return cls(year, month, day)

  @classmethod
  def from_mjdday(cls, mjdday):  # pylint: disable=invalid-name
    """Create new date object from MJD day number."""
    year, month, day = _DayNumToYMD(mjdday + _MJD_BASE)
    return cls(year, month, day)

  def __cmp__(self, other):
    """Compare this date object to another."""
    if not isinstance(other, date):
      raise AttributeError('Both objects must be datetime')
    # pylint: disable=protected-access
    return cmp(self._days, other._days)

  def strftime(self, fmt, roundofs=0):  # pylint: disable=invalid-name
    """Get datetime string in specified format from date object."""
    _ = roundofs
    if not self._struct:
      yday = self._days - _DayNum(self.year, 1, 1) + 1
      wday = _DayNumToWeekdayNum(self._days)
      self._struct = (self.year, self.month, self.day, 0, 0, 0, wday, yday, 0)
    return LocalStrftime(fmt, self._struct, '000000')


class time(object):  # pylint: disable=invalid-name,too-many-instance-attributes
  """Time-only object."""
  def __new__(cls, hour=0, minute=0, second=0, nanosecond=0):
    seconds, nanos = _SecondsNanos(hour, minute, second, nanosecond)
    self = object.__new__(cls)
    # pylint: disable=protected-access
    self.seconds, self.nanosecond = seconds, nanos
    self.hour, self.minute, self.second = hour, minute, second
    self._struct_dict = {}
    self._struct = None
    return self

  def __cmp__(self, other):
    """Compare this time object to another."""
    return (cmp(self.seconds, other.seconds)
            or cmp(self.nanosecond, other.nanosecond))

  @classmethod
  def from_secs_nanos(cls,  # pylint: disable=invalid-name
                      seconds, nanosecond=0):
    """Create new time object from seconds and nanoseconds."""
    hour, minute, second = _SecondsToHMS(seconds)
    return cls(hour, minute, second, nanosecond)

  def strftime(self,  # pylint: disable=invalid-name
               fmt, roundofs=500, fixed_leap=None):
    """Get datetime string in specified format from time object."""
    struct_key = (roundofs, fixed_leap)
    struct = self._struct_dict.get(struct_key)
    if not struct:
      secofs, micros = divmod((self.nanosecond + roundofs) // 1000, 1000000)
      if fixed_leap is not None:
        raise ValueError('No fixed_leap on time-only object')
      if secofs:
        hour, minute, second = _SecondsToHMS(self.seconds + secofs,
                                             leapok=False)
        struct0 = (0, 0, 0, hour % 24, minute, second, 0, 0, 0)
      else:
        struct0 = (0, 0, 0, self.hour, self.minute, self.second, 0, 0, 0)
      struct = (struct0, '%.06d' % micros)
      self._struct_dict[struct_key] = struct
    return LocalStrftime(fmt, struct[0], struct[1])


class datetime(  # pylint: disable=invalid-name,too-many-instance-attributes
    object
    ):
  """Date/time object."""
  def __new__(cls,  # pylint: disable=too-many-arguments
              year, month=1, day=1, hour=0, minute=0, second=0, nanosecond=0):
    days = _DayNum(year, month, day)
    if days < _GREGORIAN_SKIP_END:
      raise ValueError('Date too early')
    leap_seconds, num_seconds = _LeapInfo(days)
    seconds, nanos = _SecondsNanos(hour, minute, second, nanosecond)
    if seconds >= num_seconds:
      raise ValueError('Invalid leap second')
    self = object.__new__(cls)
    # pylint: disable=protected-access
    self._days, self.seconds, self.nanosecond = days, seconds, nanos
    self.leapseconds, self.num_seconds = leap_seconds, num_seconds
    self.year, self.month, self.day = year, month, day
    self.hour, self.minute, self.second = hour, minute, second
    self._struct_dict = {}
    return self

  @classmethod
  def from_daynum_secs_nanos(cls, daynum, seconds, nanosecond=0):
    """Create new datetime object from absolute day number, secs, and nanos."""
    year, month, day = _DayNumToYMD(daynum)
    hour, minute, second = _SecondsToHMS(seconds)
    return cls(year, month, day, hour, minute, second, nanosecond)

  @classmethod
  def from_mjdday_secs_nanos(cls, mjdday, seconds, nanosecond=0):
    """Create new datetime object from MJD day number, seconds, and nanos."""
    year, month, day = _DayNumToYMD(mjdday + _MJD_BASE)
    hour, minute, second = _SecondsToHMS(seconds)
    return cls(year, month, day, hour, minute, second, nanosecond)

  @classmethod
  def from_mjd(cls, mjd):
    """Create new datetime object from MJD day number (float)."""
    mjdday = int(mjd)
    seconds = (mjd - mjdday) * SECONDS_PER_DAY
    secint = int(seconds)
    nanosecond = int((seconds - secint) * 1.0E9)
    year, month, day = _DayNumToYMD(mjdday + _MJD_BASE)
    hour, minute, second = _SecondsToHMS(secint, leapok=False)
    return cls(year, month, day, hour, minute, second, nanosecond)

  @classmethod
  def combine(cls, date_obj, time_obj):
    """Create new datetime object from date and time objects."""
    return cls(date_obj.year, date_obj.month, date_obj.day,
               time_obj.hour, time_obj.minute, time_obj.second,
               time_obj.nanosecond)

  @classmethod
  def from_datetime_time(cls, dtime_obj, time_obj):
    """Create new datetime object from datetime and time objects."""
    offset = ((time_obj.seconds - dtime_obj.seconds + SECONDS_PER_DAY // 2)
              % SECONDS_PER_DAY - SECONDS_PER_DAY // 2)
    day_offset, seconds = divmod(dtime_obj.seconds + offset, SECONDS_PER_DAY)
    # pylint: disable=protected-access
    return cls.from_daynum_secs_nanos(dtime_obj._days + day_offset, seconds,
                                      time_obj.nanosecond)

  @classmethod
  def from_tai_day_secs(cls, daynum, second=0, nanosecond=0):
    """Create new datetime object from day/second offset from TAI epoch."""
    if daynum < 0:
      raise ValueError('Invalid day number')
    if second >= SECONDS_PER_DAY:
      raise ValueError('Bad second number')
    days, seconds = _TAIDaySecsToUTCDaySecs(daynum + _TAI_BASE, second)
    year, month, day = _DayNumToYMD(days)
    hour, minute, second = _SecondsToHMS(seconds)
    return cls(year, month, day, hour, minute, second, nanosecond)

  @classmethod
  def from_gps_week_secs(cls, week, second=0, nanosecond=0):
    """Create new datetime object from GPS week, second and nanosecond."""
    if week < 0:
      raise ValueError('Invalid week number')
    if second >= SECONDS_PER_WEEK:
      raise ValueError('Bad second number')
    weekday, daysec = divmod(second + GPS_LEAP_OFFSET, SECONDS_PER_DAY)
    daynum = week * NUM_WEEKDAYS + weekday
    days, seconds = _TAIDaySecsToUTCDaySecs(daynum + _GPS_BASE, daysec)
    year, month, day = _DayNumToYMD(days)
    hour, minute, second = _SecondsToHMS(seconds)
    return cls(year, month, day, hour, minute, second, nanosecond)

  def __cmp__(self, other):
    """Compare this datetime object to another."""
    if not isinstance(other, datetime):
      raise AttributeError('Both objects must be datetime')
    # pylint: disable=protected-access
    return (cmp(self._days, other._days) or cmp(self.seconds, other.seconds)
            or cmp(self.nanosecond, other.nanosecond))

  def strftime(self, fmt=FMT_ISO8601, roundofs=500, fixed_leap=None):
    """Get datetime string in specified format from datetime object."""
    struct_key = (roundofs, fixed_leap)
    struct = self._struct_dict.get(struct_key)
    if not struct:
      strloc = self
      secofs, nanos = divmod(self.nanosecond + roundofs, 1000000000)
      if fixed_leap is not None:
        secofs += self.leapseconds - fixed_leap
      if secofs:
        days, secs = self.tai_day_secs()
        dayofs, secs = divmod(secs + secofs, SECONDS_PER_DAY)
        strloc = datetime.from_tai_day_secs(days + dayofs, secs, nanos)
      # pylint: disable=protected-access
      yday = strloc._days - _DayNum(strloc.year, 1, 1) + 1
      wday = _DayNumToWeekdayNum(strloc._days)
      struct = ((strloc.year, strloc.month, strloc.day,
                 strloc.hour, strloc.minute, strloc.second, wday, yday, 0),
                '%.06d' % (nanos // 1000))
      self._struct_dict[struct_key] = struct
    return LocalStrftime(fmt, struct[0], struct[1])

  def tai_day_secs(self):
    """Get offset in days and seconds from TAI epoch, from datetime object."""
    days = self._days - _TAI_BASE
    if days < 0:
      raise ValueError('Date precedes TAI origin')
    seconds = self.seconds + self.leapseconds
    day_offset, seconds = divmod(seconds, SECONDS_PER_DAY)
    return days + day_offset, seconds

  def gps_weeks_secs_nanos(self, roundofs=0):
    """Get GPS weeks, seconds, and nanoseconds from datetime object."""
    days = self._days - _GPS_BASE
    if days < 0:
      raise ValueError('Date precedes GPS origin')
    nanos = self.nanosecond + roundofs
    seconds = self.seconds + self.leapseconds - GPS_LEAP_OFFSET
    if nanos >= 1000000000:
      nanos -= 1000000000
      seconds += 1
    day_offset, seconds = divmod(seconds, SECONDS_PER_DAY)
    week, dow = divmod(days + day_offset, NUM_WEEKDAYS)
    return week, dow * SECONDS_PER_DAY + seconds, nanos

  def diff_secs(self, other):
    """Get difference in seconds between two datetime objects."""
    if not isinstance(other, datetime):
      raise AttributeError('Both objects must be datetime')
    # pylint: disable=protected-access
    diff = (self.nanosecond - other.nanosecond) / 1.0E9
    diff += self.seconds - other.seconds + self.leapseconds - other.leapseconds
    diff += (self._days - other._days) * SECONDS_PER_DAY
    return diff
