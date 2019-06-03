"""Generic data definitions."""

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


class Debuggable(object):  # pylint: disable=too-few-public-methods
  """Base class for all objects, providing methods for debugging."""
  # The IV/CV methods expect that class "variables" are all upper case,
  # and that instance variables are all lower case.
  # This assumption can be overridden with the INCLUDE/EXCLUDE variables.
  #
  # These variables are merged across the MRO chain, so they only need
  # to reflect the class where they appear.  Since the IV/CV methods are
  # only intended for debugging, this processing is done within, rather
  # than at definition time.
  _CV_EXCLUDE = ['IV', '_IV_INCLUDE', '_IV_EXCLUDE',
                 'CV', '_CV_INCLUDE', '_CV_EXCLUDE']

  @classmethod
  def _Collect(cls, name):
    """Merge sets from the specified variable across the MRO chain."""
    result = set()
    for this in cls.__mro__:
      result |= set(getattr(this, name, []))
    return result

  @classmethod
  def CV(cls):  # pylint: disable=invalid-name
    """Get dict of class variables (for debugging)."""
    # Uses the naming convention for default filtering
    include = cls._Collect('_CV_INCLUDE')
    exclude = cls._Collect('_CV_EXCLUDE')
    result = {}
    for name in dir(cls):
      if name in include:
        result[name] = getattr(cls, name)
        continue
      if name in exclude:
        continue
      if not name.startswith('__') and name == name.upper():
        result[name] = getattr(cls, name)
    return result

  def IV(self):  # pylint: disable=invalid-name
    """Get dict of instance variables (for debugging)."""
    # Uses the naming convention for default filtering
    include = self._Collect('_IV_INCLUDE')
    exclude = self._Collect('_IV_EXCLUDE')
    result = {}
    for name in dir(self):
      if name in include:
        result[name] = getattr(self, name)
        continue
      if name in exclude:
        continue
      if not name.startswith('__') and name == name.lower():
        result[name] = getattr(self, name)
    return result


class BitString(Debuggable):  # pylint: disable=too-few-public-methods
  """Class for bitstring data."""
  __slots__ = ('raw', 'nbits', 'data', 'lpad', 'rpad')

  def __init__(self, data, rpad=0, lpad=0):
    """Derive bitstring item from array of longs."""
    total = 0
    nbits = 0
    for value in data:
      total = (total << 32) | value
      nbits += 32
    self.raw = total
    self.nbits = nbits - lpad - rpad
    self.data = total >> rpad
    if self.nbits != nbits:
      self.data &= (1 << nbits) - 1
    self.lpad = lpad
    self.rpad = rpad

  # Note that the following methods wrap the return values with int()
  # to convert to a plain (non-long) int where possible.

  def GetLpad(self):
    """Get left-side (high-order) padding from item."""
    return int((self.raw >> (self.nbits + self.rpad)) & ((1 << self.lpad) - 1))

  def GetRpad(self):
    """Get right-side (low-order) padding from item."""
    return int(self.raw & ((1 << self.rpad) - 1))

  def GetLField(self, pos, size):
    """Get field from given position (from left) and size."""
    return int((self.data >> (self.nbits - pos - size)) & ((1 << size) - 1))

  def GetRField(self, pos, size):
    """Get field from given position (from right) and size."""
    return int((self.data >> pos) & ((1 << size) - 1))
