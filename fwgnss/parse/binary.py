"""Generic code for parsing binary GNSS messages."""

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

import collections
import struct

from . import generic


ENDIAN_PREFIXES = {'little': ['<'], 'big': ['>']}

StructError = struct.error  # pylint: disable=invalid-name


class Constants(generic.Constants):  # pylint: disable=too-few-public-methods
  """Class which holds various constant definitions."""


def MakeStruct(prefix, pat_list):
  """Create a Struct object, based on a given pattern."""
  return struct.Struct(' '.join(prefix + list(pat_list)))


def MakeBasicParser(name, name_list, prefix, pat_list):
  """Create a parser based on a list of field names and list of patterns."""
  tuple_type = collections.namedtuple(name, name_list)
  return [tuple_type, MakeStruct(prefix, pat_list)]


def MakeParser(parser_name,  # pylint: disable=too-many-locals
               prefix, struct_dict, pattern):
  """Create a parser with a given name and struct pattern."""
  pat_list = [x.split(':') for x in pattern.split()]
  name_list = []
  group_list = []
  fmt_list = []
  idx = 0
  for name, fmt in pat_list:
    name_list.append(name)
    fmt_split = fmt.split('*')
    fmt = fmt_split[0]
    count = int(fmt_split[1]) if len(fmt_split) > 1 else None
    if len(fmt) == 1:
      if not count:
        fmt_list.append(fmt)
      else:
        group_list.append((idx, count))
        fmt_list.append('%d%s' % (count, fmt))
    else:
      parser = struct_dict[fmt]
      struc_fmt = '%ds' % parser[1].size
      group_list.append((idx, count, parser))
      fmt_list.extend([struc_fmt] * count)
    idx += count or 1
  if group_list:
    return tuple(MakeBasicParser(parser_name, name_list, prefix, fmt_list)
                 + [tuple(group_list)])
  return tuple(MakeBasicParser(parser_name, name_list, prefix, fmt_list))


def DefineParser(name, prefix, struct_dict, pattern):
  """Define a parser and add it to a dictionary."""
  struct_dict[name] = MakeParser(name, prefix, struct_dict, pattern)


class BinaryItem(generic.Item):
  """Generic binary item from extracter."""

  __slots__ = ()


class BinaryDataItem(BinaryItem):
  """Generic binary non-response item from extracter."""

  __slots__ = ()


class BinaryResponseItem(generic.ResponseItem, BinaryItem):
  """Base class for binary command-response extracted items."""

  __slots__ = ()


class Extracter(generic.Extracter):
  """Generic binary message extracter."""
  ENDIANNESS = None

  @staticmethod
  def IsBinary(item):
    return isinstance(item, BinaryItem)


class Parser(generic.Parser):
  """Generic binary message parser."""

  class MessageParser(generic.Parser.ParseItem):
    """Base class for message-specific parsers."""
    PARSER = None  # Dummy for pylint - overridden in subclasses

    @classmethod
    def Parse(cls, item):
      """Top-level item parser."""
      parser = cls.PARSER
      return cls._ParseItem(parser, item.data)

    @classmethod
    def _ParseItem(cls, parser, data):
      """General recursive item parser."""
      value = parser[1].unpack(data)
      if len(parser) < 3:
        return parser[0]._make(value)
      result = []
      idx = 0
      for entry in parser[2]:
        offset, count = entry[:2]
        result.extend(value[idx:offset])
        if len(entry) == 2:
          result.append(tuple(value[offset:offset+count]))
          idx = offset + count
          continue
        subparser = entry[2]
        if not count:
          result.append(cls._ParseItem(subparser, value[offset]))
        else:
          val_list = value[offset:offset+count]
          result.append(tuple([cls._ParseItem(subparser, x) for x in val_list]))
        idx += offset + (count or 1)
      result.extend(value[idx:])
      return parser[0]._make(result)


class Decoder(generic.Decoder):
  """Generic binary message decoder."""

  ObservationSet = collections.namedtuple('ObsSet', 'dtime sat_obs')
  SatObservation = collections.namedtuple(
      'SatObs',
      'system sat_id knum idx spare sig_obs'
      )
  SigObservation = collections.namedtuple(
      'SigObs',
      'signal snr track_time track_max slip_counter slip_warn '
      + 'wavelength pseudorange doppler phase'
      )
