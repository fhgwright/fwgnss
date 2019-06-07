"""GNSS parser for NMEA-0183 data."""

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
import operator
import re

try:
  reduce
except NameError:
  from functools import reduce  # pylint: disable=redefined-builtin

from . import generic


class Constants(generic.Constants):  # pylint: disable=too-few-public-methods
  """Class which holds various constant definitions."""

  # Signal ID codes (for, e.g., GxGSV) - not unique across systems
  SIGNAL_ID_L1CA = 1
  SIGNAL_DECODE = {1: 'L1 C/A'}


class Sentence(generic.TextItem):
  """NMEA sentence from extracter."""
  PREFIX_IN = b'$'

  PREFIX = '$'
  SEPARATOR = ','
  CHECKSUM_FLAG = '*'
  EOL = '\r\n'

  TYPE_RE = re.compile(r'[A-Z]{2,5}[0-9]?$')

  PATTERN = PREFIX + '%s' + CHECKSUM_FLAG + '%02X'
  LINE = PATTERN + EOL
  NO_CKS_PAT = PREFIX + '%s'
  NO_CKS_LINE = NO_CKS_PAT + EOL

  __slots__ = ('has_checksum',)

  def __init__(self, data, length=None, msgtype=None, has_checksum=False):
    super(Sentence, self).__init__(data, length, msgtype)
    self.has_checksum = has_checksum

  @classmethod
  def Extract(cls, extracter):  # pylint: disable=too-many-return-statements
    """Extract an NMEA sentence from the input stream."""
    # Valid line must have at least two chars and start with prefix
    if len(extracter.line) < 2 or not extracter.line.startswith(cls.PREFIX_IN):
      return None, 0

    length, endlen = extracter.GetEOL()
    if not endlen:
      return None, 0  # Discard unterminated line

    # Note that Hemisphere response lines will also match up to this point
    # (if this extracter precedes the Control extracter), but will be
    # rejected by the re.match below.  Since response lines are rare, it's
    # not worth worrying about the cost of getting all the way into the
    # re.match before rejecting them.

    # Keep bytes version of body for checksum
    bbody = extracter.line[1:length]
    body = extracter.GetText(bbody)
    if not body:  # Here if it's not really NMEA
      return None, 0
    data = body.split(cls.SEPARATOR)
    if len(data) < 2 or not cls.TYPE_RE.match(data[0]):
      return None, 0
    last = data[-1]
    has_checksum = len(last) >= 3 and last[-3] == cls.CHECKSUM_FLAG
    if has_checksum:
      try:
        checksum = int(last[-2:], 16)
      except ValueError:
        return None, 0
      data[-1] = last[:-3]
      actual_checksum = cls.ChecksumBytes(bbody[:-3])
      if actual_checksum != checksum:
        return None, 0
    item = cls.Make(data=data, msgtype=data[0].upper(),
                    has_checksum=has_checksum)
    return item, length + endlen

  @staticmethod
  def ChecksumBytes(data):
    """Compute NMEA checksum of data supplied as bytes."""
    return reduce(operator.xor, bytearray(data), 0)

  @classmethod
  def _ChecksumString(cls, data):
    """Compute NMEA checksum of data supplied as string."""
    return reduce(operator.xor, bytearray(data, encoding=cls.TEXT_ENCODING), 0)

  def Contents(self):
    line = self.SEPARATOR.join(self.data)
    if self.has_checksum:
      checksum = self._ChecksumString(line)
      return self.LINE % (line, checksum)
    return self.NO_CKS_LINE % line

  def Summary(self, full=False):
    line = self.SEPARATOR.join(self.data)
    if full and self.has_checksum:
      checksum = self._ChecksumString(line)
      return self.PATTERN % (line, checksum)
    return self.NO_CKS_PAT % line

  def LogText(self):
    return self.SEPARATOR.join(self.data)


class NmeaExtracter(generic.Extracter):
  """Class for NMEA extracter."""
  # Use this for vendor-specific subclassing.
  def __new__(cls, infile=None):
    self = super(NmeaExtracter, cls).__new__(cls, infile)
    self.AddExtracter(Sentence)
    self.parse_map['NMEA'] = Sentence.PARSE_CLASS
    return self


def MakeParser(name, pattern):
  """Create a parser with the specified name and field pattern."""
  parser = collections.namedtuple(name, pattern)
  return parser, len(parser._fields)


class NmeaParser(generic.Parser):
  """Class for NMEA sentence parser."""
  # Use this for vendor-specific subclassing.
  NMEA_DICT = {}

  @classmethod
  def GetParser(cls, msgtype, subtype=None):
    """Get parser for this message type."""
    _ = subtype
    return cls.NMEA_DICT.get(msgtype)

  @staticmethod
  def ParseData(parser, item):
    """Return parsed object for this item's data."""
    if item.length < parser.MIN_LENGTH:
      item.parse_error = 'Truncated %s sentence' % item.msgtype
      return None
    return parser.Parse(item)

  class ParseItem(  # pylint: disable=too-few-public-methods
      generic.Parser.ParseItem
      ):
    """Base class for type-specific parsers."""

  class ParseGGA(ParseItem):
    """Parser for GxGGA sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGGA',
        'time lats lons qual num_sats hdop alts geoids age refid'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxGGA item."""
      data = item.data
      return cls.PARSED(
          time=data[1], lats=tuple(data[2:4]), lons=tuple(data[4:6]),
          qual=data[6],
          num_sats=data[7], hdop=data[8],
          alts=tuple(data[9:11]), geoids=tuple(data[11:13]),
          age=data[13], refid=data[14],
          )
  NMEA_DICT['GPGGA'] = ParseGGA

  class ParseGNS(ParseItem):
    """Parser for GxGNS sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGNS',
        'time lats lons mode num_sats hdop alts geoids age refid navstat'
        )
    MIN_LENGTH -= 1

    @classmethod
    def Parse(cls, item):
      """Parse the xxGNS item."""
      data = item.data
      try:
        navstat = data[13]
      except IndexError:
        navstat = ''
      return cls.PARSED(
          time=data[1], lats=tuple(data[2:4]), lons=tuple(data[4:6]),
          mode=data[6],
          num_sats=data[7], hdop=data[8],
          alts=(data[9], 'M'), geoids=(data[10], 'M'),
          age=data[11], refid=data[12], navstat=navstat,
          )
  NMEA_DICT['GPGNS'] = ParseGNS
  NMEA_DICT['GLGNS'] = ParseGNS
  NMEA_DICT['GNGNS'] = ParseGNS

  class ParseGLL(ParseItem):
    """Parser for GxGLL sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGLL',
        'lats lons time status'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxGLL item."""
      data = item.data
      return cls.PARSED(
          lats=tuple(data[1:3]), lons=tuple(data[3:5]),
          time=data[5], status=data[6],
          )
  NMEA_DICT['GPGLL'] = ParseGLL

  class ParseVTG(ParseItem):
    """Parser for GxVTG sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxVTG',
        'track_t track_m speed_n speed_k mode'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxVTG item."""
      data = item.data
      return cls.PARSED(
          track_t=tuple(data[1:3]), track_m=tuple(data[3:5]),
          speed_n=tuple(data[5:7]), speed_k=tuple(data[7:9]),
          mode=data[9],
          )
  NMEA_DICT['GPVTG'] = ParseVTG

  class ParseZDA(ParseItem):
    """Parser for GxZDA sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxZDA',
        'time day month year zone'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxZDA item."""
      data = item.data
      return cls.PARSED(
          time=data[1], day=data[2], month=data[3], year=data[4],
          zone=tuple(data[5:7]),
          )
  NMEA_DICT['GPZDA'] = ParseZDA

  class ParseRMC(ParseItem):
    """Parser for GxRMC sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxRMC',
        'time status lats lons speed_n track_t '
        + 'day month year mag_var mode navstat'
        )
    MIN_LENGTH -= 1

    @classmethod
    def Parse(cls, item):
      """Parse the xxRMC item."""
      data = item.data
      try:
        navstat = data[13]
      except IndexError:
        navstat = ''
      return cls.PARSED(
          time=data[1], status=data[2],
          lats=tuple(data[3:5]), lons=tuple(data[5:7]),
          speed_n=(data[7], 'N'), track_t=(data[8], 'N'),
          day=data[9][:2], month=data[9][2:4], year=data[9][4:],
          mag_var=tuple(data[10:12]), mode=data[12], navstat=navstat,
          )
  NMEA_DICT['GPRMC'] = ParseRMC

  class ParseDTM(ParseItem):
    """Parser for GxDTM sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxDTM',
        'datum subdiv lats lons alts, ref_dtm'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxDTM item."""
      data = item.data
      return cls.PARSED(
          datum=data[1], subdiv=data[2],
          lats=tuple(data[3:5]), lons=tuple(data[5:7]),
          alts=(data[7], 'M'), ref_dtm=data[8],
          )
  NMEA_DICT['GPDTM'] = ParseDTM

  class ParseGSA(ParseItem):
    """Parser for GxGSA sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGSA',
        'acq_mode pos_mode sat_list pdop hdop vdop system'
        )
    MIN_LENGTH -= 1

    @classmethod
    def Parse(cls, item):
      """Parse the xxGSA item."""
      data = item.data
      try:
        sysid = data[18]
      except IndexError:
        sysid = ''
      return cls.PARSED(
          acq_mode=data[1], pos_mode=data[2],
          sat_list=tuple([s for s in data[3:15] if s]),
          pdop=data[15], hdop=data[16], vdop=data[17],
          system=sysid,
          )
  NMEA_DICT['GPGSA'] = ParseGSA
  NMEA_DICT['GNGSA'] = ParseGSA

  class ParseGRS(ParseItem):
    """Parser for GxGRS sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGRS',
        'time mode residuals system signal'
        )
    MIN_LENGTH -= 2

    @classmethod
    def Parse(cls, item):
      """Parse the xxGRS item."""
      data = item.data
      sysid, sigid = '', ''
      try:
        sysid = data[15]
        sigid = data[16]
      except IndexError:
        pass
      return cls.PARSED(
          time=data[1], mode=data[2],
          residuals=tuple([r for r in data[3:15] if r]),
          system=sysid, signal=sigid,
          )
  NMEA_DICT['GPGRS'] = ParseGRS

  class ParseGSV(ParseItem):
    """Parser for GxGSV sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGSV',
        'num_msgs msg_num num_sats sat_views signal system'
        )
    SAT_VIEW = collections.namedtuple(
        'GxGSVsat',
        'sat elev az snr'  # Must match order in sentence
        )
    MIN_LENGTH -= 1  # system is optional
    MIN_LENGTH += 4 - 1  # for a single sat_view
    FULL_MIN_LENGTH = MIN_LENGTH + 4 * (4 - 1)   # for 4 sat_views

    @classmethod
    def ParseCommon(cls, item, sysid):
      """Parse the xxGSV item."""
      data = item.data
      if item.length < cls.FULL_MIN_LENGTH:
        try:
          num_msgs, msg_num, num_sats = map(int, data[1:4])
        except ValueError:
          num_msgs, msg_num, num_sats = (0, 0, 4)
        if msg_num == num_msgs:
          num_entries = num_sats - (msg_num - 1) * 4
        sats_end = 4 * num_entries * 4
      else:
        sats_end = 20
      sat_data = zip(*[iter(data[4:sats_end])]*4)
      try:
        sigid = data[sats_end]
      except IndexError:
        sigid = ''
      return cls.PARSED(
          num_msgs=data[1], msg_num=data[2], num_sats=data[3],
          sat_views=tuple([cls.SAT_VIEW._make(s) for s in sat_data if s[0]]),
          signal=sigid, system=sysid,
          )

  class ParseGPGSV(ParseGSV):
    """Parser for GPGSV sentence."""
    SYSTEM_ID = str(Constants.SYSTEM_ID_GPS)

    @classmethod
    def Parse(cls, item):
      """Parse the GPGSV item."""
      return cls.ParseCommon(item, cls.SYSTEM_ID)
  NMEA_DICT['GPGSV'] = ParseGPGSV

  class ParseGLGSV(ParseGSV):
    """Parser for GLGSV sentence."""
    SYSTEM_ID = str(Constants.SYSTEM_ID_GLONASS)

    @classmethod
    def Parse(cls, item):
      """Parse the GLGSV item."""
      return cls.ParseCommon(item, cls.SYSTEM_ID)
  NMEA_DICT['GLGSV'] = ParseGLGSV

  class ParseGST(ParseItem):
    """Parser for GxGST sentence."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGST',
        'time rms_err major_err minor_err major_dir lat_err lon_err alt_err'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the xxGST item."""
      return cls.PARSED._make(item.data[1:9])
  NMEA_DICT['GPGST'] = ParseGST

  class ParseRRE(ParseItem):
    """Parser for GxRRE sentence."""
    PARSED, _ = MakeParser(
        'GxRRE',
        'num_used residuals horiz_err vert_err'
        )
    SAT_DATA = collections.namedtuple(
        'RREsat',
        'sat value'  # Must match order in sentence
        )
    MIN_LENGTH = 4

    @classmethod
    def Parse(cls, item):
      """Parse the xxRRE item."""
      data = item.data
      num_used = data[1]
      try:
        num = int(num_used)
      except ValueError:
        num = 0
      num2 = num * 2
      if item.length < cls.MIN_LENGTH + num2:
        item.parse_error = 'Truncated %s sentence' % item.msgtype
        return None
      sat_data = zip(*[iter(data[2:num2+2])]*2)
      return cls.PARSED(
          num_used=num_used,
          residuals=tuple([cls.SAT_DATA._make(s) for s in sat_data]),
          horiz_err=data[2 + num2], vert_err=data[3 + num2],
          )
  NMEA_DICT['GPRRE'] = ParseRRE

  class ParseGBS(ParseItem):
    """Parser for GxGBS sentences."""
    PARSED, MIN_LENGTH = MakeParser(
        'GxGBS',
        'time lat_err lon_err alt_err bad_sat fault_prob '
        + 'range_bias range_bias_sd system signal'
        )

    @classmethod
    def Parse(cls, item):
      """Parse the GxGBS sentence."""
      return cls.PARSED._make(item.data[1:11])
  NMEA_DICT['GPGBS'] = ParseGBS

Sentence.PARSE_CLASS = NmeaParser


class NmeaDecoder(generic.Decoder):  # pylint: disable=too-many-public-methods
  """Class for NMEA sentence decoder."""
  # Use this for vendor-specific subclassing.
  DECODER_DICT = {}

  def __init__(self):
    super(NmeaDecoder, self).__init__()
    self._last_gsa = {}
    self._last_grs = {}
    self._gsv_dict = {}
    self._gsv_time = None

  @staticmethod
  def DecodeInt(value, base=10):
    """Decode integer value."""
    if value:
      return int(value, base)
    return None

  @staticmethod
  def DecodeFloat(value):
    """Decode floating-point value."""
    if value:
      return float(value)
    return None

  def DecodeNmeaTime(self, field, store=True):
    """Decode time from NMEA fields."""
    try:
      hour = int(field[:2])
      minute = int(field[2:4])
      second = int(field[4:6])
      fraction = float(field[6:])
    except ValueError:
      return None
    return self.MakeTimeHMSN(hour, minute, second, int(fraction * 1E9), store)

  def DecodeNmeaDateTime(self, parsed, time, store=True):
    """Convert parsed date and supplied time to datetime, & optionally store."""
    year = int(parsed.year)
    month = int(parsed.month)
    day = int(parsed.day)
    return self.MakeDateTimeYMDT(year, month, day, time, store)

  @staticmethod
  def DecodeNmeaLL1(data, hemi_vals):
    """Decode lat or lon from value and hemisphere indicator."""
    try:
      value = float(data[0])
    except ValueError:
      return None, None
    hemi = data[1]
    degrees = int(value) // 100
    value = degrees + (value - degrees * 100) / 60.0
    if hemi == hemi_vals[0]:
      hemi = ''
    elif hemi == hemi_vals[1]:
      hemi = ''
      value = -value
    return value, hemi

  @classmethod
  def DecodeNmeaLL(cls, parsed):
    """Decode lat/lon from NMEA format."""
    lat, lat_h = cls.DecodeNmeaLL1(parsed.lats, 'NS')
    lon, lon_h = cls.DecodeNmeaLL1(parsed.lons, 'EW')
    return lat, lat_h, lon, lon_h

  @staticmethod
  def DecodeNmeaAlt(data):
    """Decode NMEA altitude."""
    if not data[0]:
      return None, None
    return float(data[0]), data[1]

  @staticmethod
  def DecodeMagVar(data):
    """decode magnetic variation from value and hemisphere indicator."""
    if not data[0]:
      return None, None
    value = float(data[0])
    hemi = data[1]
    if hemi == 'E':
      hemi = ''
    elif hemi == 'W':
      hemi = ''
      value = -value
    return value, hemi

  @staticmethod
  def DecodeSatNum(num):
    """Decode satellite number into separate system and number."""
    if num is None:
      sat_type, sat_id = None, None
    elif num <= 32:
      sat_type, sat_id = Constants.SAT_TYPE_GPS, num
    elif num <= 64:
      sat_type, sat_id = Constants.SAT_TYPE_SBAS, num + 87
    else:
      sat_type, sat_id = Constants.SAT_TYPE_GLONASS, num - 64
    return sat_type, sat_id

  DecGGA = collections.namedtuple(
      'dGGA',
      'time lat lat_h lon lon_h num_sats hdop alt alt_u geoid geoid_u age'
      )
  def DecodeGGA(self, item):  # pylint: disable=too-many-locals
    """Decode xxGGA sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    lat, lat_h, lon, lon_h = self.DecodeNmeaLL(parsed)
    num_sats = self.DecodeInt(parsed.num_sats)
    hdop = self.DecodeFloat(parsed.hdop)
    alt, alt_u = self.DecodeNmeaAlt(parsed.alts)
    geoid, geoid_u = self.DecodeNmeaAlt(parsed.geoids)
    age = self.DecodeFloat(parsed.age)
    return self.DecGGA(
        time, lat, lat_h, lon, lon_h, num_sats, hdop,
        alt, alt_u, geoid, geoid_u, age)
  DECODER_DICT[NmeaParser.ParseGGA] = DecodeGGA
  DECODER_DICT[NmeaParser.ParseGNS] = DecodeGGA

  GGA_QUALITY_DECODE = {
      '0': 'Invalid',
      '1': 'Autonomous',
      '2': 'Differential',
      '4': 'RTK Fixed',
      '5': 'RTK Float',
  }

  NAV_MODE_DECODE = {
      'N': 'No fix',
      'A': 'Autonomous',
      'D': 'Differential',
      'P': 'Precise',
      'R': 'RTK Fixed',
      'F': 'RTK Float',
      'E': 'Estimated',
      'M': 'Manual input',
      'S': 'Simulator',
  }

  DecGLL = collections.namedtuple('dGLL', 'time lat lat_h lon lon_h')
  def DecodeGLL(self, item):
    """Decode xxGLL sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    lat, lat_h, lon, lon_h = self.DecodeNmeaLL(parsed)
    return self.DecGLL(time, lat, lat_h, lon, lon_h)
  DECODER_DICT[NmeaParser.ParseGLL] = DecodeGLL

  DecVTG = collections.namedtuple('dVTG', 'track_t track_m speed_n speed_k')
  def DecodeVTG(self, item):
    """Decode xxVTG sentence."""
    parsed = item.parsed
    track_t = self.DecodeFloat(parsed.track_t[0])
    track_m = self.DecodeFloat(parsed.track_m[0])
    speed_n = self.DecodeFloat(parsed.speed_n[0])
    speed_k = self.DecodeFloat(parsed.speed_k[0])
    return self.DecVTG(track_t, track_m, speed_n, speed_k)
  DECODER_DICT[NmeaParser.ParseVTG] = DecodeVTG

  UNITS_MAP = {
      'T': 'True',
      'M': 'Magnetic',
      'N': 'Kt',
      'K': 'Kph',
      }

  DecZDA = collections.namedtuple('dZDA', 'time dtime zone')
  def DecodeZDA(self, item):
    """Decode xxZDA sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    dtime = self.DecodeNmeaDateTime(parsed, time)
    zone_hour, zone_min = map(int, parsed.zone)
    zone = zone_hour * 60 + zone_min
    return self.DecZDA(time, dtime, zone)
  DECODER_DICT[NmeaParser.ParseZDA] = DecodeZDA

  DecRMC = collections.namedtuple(
      'dRMC',
      'time dtime lat lat_h lon lon_h speed_n track_t mag_var mag_var_h'
      )
  def DecodeRMC(self, item):
    """Decode xxRMC sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    lat, lat_h, lon, lon_h = self.DecodeNmeaLL(parsed)
    speed_n = self.DecodeFloat(parsed.speed_n[0])
    track_t = self.DecodeFloat(parsed.track_t[0])
    mag_var, mag_var_h = self.DecodeMagVar(parsed.mag_var)
    dtime = self.DecodeNmeaDateTime(parsed, time)
    return self.DecRMC(time, dtime, lat, lat_h, lon, lon_h,
                       speed_n, track_t, mag_var, mag_var_h)
  DECODER_DICT[NmeaParser.ParseRMC] = DecodeRMC

  RMC_STATUS_DECODE = {'A': 'Valid', 'V': 'Invalid'}

  RMC_NAVSTAT_DECODE = {
      'S': 'Safe',
      'C': 'Caution',
      'U': 'Unsafe',
      'V': 'Not valid',
  }

  DecDTM = collections.namedtuple(
      'dDTM', 'latoff latoff_h lonoff lonoff_h altoff'
      )
  def DecodeDTM(self, item):
    """Decode xxDTM sentence."""
    parsed = item.parsed
    latoff, latoff_h, lonoff, lonoff_h = self.DecodeNmeaLL(parsed)
    altoff = self.DecodeFloat(parsed.alts[0])
    return self.DecDTM(latoff, latoff_h, lonoff, lonoff_h, altoff)
  DECODER_DICT[NmeaParser.ParseDTM] = DecodeDTM

  GSA_VIEW = collections.namedtuple(
      'dGSAsat',
      'sat type num'
      )
  @classmethod
  def _MakeGSA_VIEW(cls, sat):  # pylint: disable=invalid-name
    sat = int(sat)
    sat_type, num = cls.DecodeSatNum(sat)
    return cls.GSA_VIEW(sat, sat_type, num)

  @classmethod
  def _MakeResiduals(cls, sat_entry):
    sat, sat_type, num = sat_entry[0]
    return cls.SatResidual(sat=sat, type=sat_type, num=num, value=sat_entry[1])

  SigResiduals = collections.namedtuple('SigRes', 'signal residuals')

  DecGSA = collections.namedtuple(
      'dGSA',
      'acq_mode pos_mode sat_list pdop hdop vdop system sig_residuals'
      )
  def DecodeGSA(self, item):  # pylint: disable=too-many-locals
    """Decode xxGSA sentence."""
    parsed = item.parsed
    try:
      system = self.DecodeInt(parsed.system) or Constants.SYSTEM_ID_GPS
      pos_mode = int(parsed.pos_mode)
      pdop, hdop = self.DecodeFloat(parsed.pdop), self.DecodeFloat(parsed.hdop)
      vdop = self.DecodeFloat(parsed.vdop)
    except ValueError:
      item.decode_error = 'Garbled %s sentence' % item.msgtype
      return None
    try:
      sat_list = list(map(self._MakeGSA_VIEW, parsed.sat_list))
    except ValueError:
      item.decode_error = 'Bad %s satellite data' % item.msgtype
      return None
    res_list = []
    grs_dict = self._last_grs.get(system)
    if grs_dict:
      sig_list = list(grs_dict.keys())
      sig_list.sort()
      for signal in sig_list:
        residuals = grs_dict.get(signal)
        if residuals is not None:
          if len(residuals) != len(sat_list):
            item.decode_error = ('Residual mismatch in %s, %d sats != %d values'
                                 % (item.msgtype,
                                    len(sat_list), len(residuals)))
          res_entry = map(self._MakeResiduals, zip(sat_list, residuals))
          res_list.append(self.SigResiduals(signal, tuple(res_entry)))
    else:
      self._last_gsa[system] = sat_list
    return self.DecGSA(acq_mode=parsed.acq_mode, pos_mode=pos_mode,
                       sat_list=tuple(sat_list),
                       pdop=pdop, hdop=hdop, vdop=vdop,
                       system=system,
                       sig_residuals=tuple(res_list))
  DECODER_DICT[NmeaParser.ParseGSA] = DecodeGSA

  GSA_ACQ_MODE_DECODE = {'M': 'Manual', 'A': 'Automatic'}
  GSA_POS_MODE_DECODE = {'1': 'No fix', '2': '2D', '3': '3D'}

  DecGRS = collections.namedtuple(
      'dGRS',
      'time mode residuals system signal sat_residuals'
      )
  def DecodeGRS(self, item):
    """Decode xxGRS sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    try:
      system = self.DecodeInt(parsed.system) or Constants.SYSTEM_ID_GPS
      signal = self.DecodeInt(parsed.signal) or Constants.SIGNAL_ID_L1CA
      mode = int(parsed.mode)
      residuals = list(map(float, parsed.residuals))
    except ValueError:
      item.decode_error = 'Garbled %s sentence' % item.msgtype
      return None
    saved = self._last_grs.setdefault(system, {})
    res_list = None
    sat_list = self._last_gsa.get(system)
    if sat_list:
      if len(sat_list) != len(residuals):
        item.decode_error = ('Residual mismatch in %s, %d sats != %d values'
                             % (item.msgtype,
                                len(sat_list), len(residuals)))
      res_list = tuple(map(self._MakeResiduals, zip(sat_list, residuals)))
    else:
      saved[signal] = residuals
    return self.DecGRS(time=time, mode=mode, residuals=tuple(residuals),
                       system=system, signal=signal, sat_residuals=res_list)
  DECODER_DICT[NmeaParser.ParseGRS] = DecodeGRS

  GRS_MODE_DECODE = {0: 'Last used', 1: 'Recomputed'}

  GSV_VIEW = collections.namedtuple(
      'dGSVsat',
      'sat type num elev az snr'
      )
  @classmethod
  def _MakeGSV_VIEW(cls, sat_view):  # pylint: disable=invalid-name
    sat = int(sat_view.sat)
    sat_type, num = cls.DecodeSatNum(sat)
    elev = sat_view.elev
    elev = int(elev) if elev else None
    azim = sat_view.az
    azim = int(azim) if azim else None
    snr = sat_view.snr
    snr = int(snr) if snr else None
    return cls.GSV_VIEW(sat=sat, type=sat_type, num=num,
                        elev=elev, az=azim, snr=snr)

  DecGSV = collections.namedtuple(
      'dGSV',
      'time system signal in_view tracked sat_views'
      )
  @classmethod
  def _DumpGSV(cls, # pylint: disable=too-many-arguments
               time, system, signal, in_view, sat_views):
    tracked = sum([sat.snr is not None for sat in sat_views])
    return cls.DecGSV(time=time, system=system, signal=signal,
                      in_view=in_view, tracked=tracked,
                      sat_views=tuple(sat_views))

  def DecodeGSV(self, item):
    """Decode xxGSV sentence."""
    parsed = item.parsed
    try:
      signal = self.DecodeInt(parsed.signal) or Constants.SIGNAL_ID_L1CA
      in_view, system = int(parsed.num_sats), int(parsed.system)
      num_msgs, msg_num = int(parsed.num_msgs), int(parsed.msg_num)
    except ValueError:
      item.decode_error = 'Garbled %s sentence' % item.msgtype
      return None
    if num_msgs < 1 or msg_num < 1 or in_view < 0 or msg_num > num_msgs:
      item.decode_error = 'Bad %s parameters' % item.msgtype
      return None
    try:
      sat_views = list(map(self._MakeGSV_VIEW, parsed.sat_views))
    except ValueError:
      item.decode_error = 'Bad %s satellite data' % item.msgtype
      return None
    key = (system, signal)
    initial_entry = [num_msgs, 0, in_view, []]
    entry = self._gsv_dict.get(key)
    if not entry:
      entry = initial_entry
      self._gsv_dict[key] = entry
      self._gsv_time = self.last_time
    if num_msgs != entry[0] or msg_num != entry[1] + 1 or in_view != entry[2]:
      error_message = (
          'Unexpected %s sequence, %d/%d/%d != %d/%d/%d'
          % (item.msgtype,
             num_msgs, msg_num, in_view,
             entry[0], entry[1] + 1, entry[2])
          )
      error_data = self._DumpGSV(
          time=self._gsv_time, system=system, signal=signal,
          in_view=(entry[1] and entry[2]), sat_views=entry[3]
          )
      item.decode_error = (error_message, error_data)
      entry = initial_entry
      self._gsv_time = self.last_time
    entry[1] = msg_num
    entry[3].extend(sat_views)
    self._gsv_dict[key] = entry
    if msg_num != num_msgs:
      return None
    del self._gsv_dict[key]
    return self._DumpGSV(
        time=self._gsv_time, system=system, signal=signal,
        in_view=entry[2], sat_views=entry[3]
        )
  DECODER_DICT[NmeaParser.ParseGPGSV] = DecodeGSV
  DECODER_DICT[NmeaParser.ParseGLGSV] = DecodeGSV

  DecGST = collections.namedtuple(
      'dGST',
      'time rms_err major_err minor_err major_dir lat_err lon_err alt_err'
      )
  def DecodeGST(self, item):
    """Decode xxGST sentence."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    rms_err = self.DecodeFloat(parsed.rms_err)
    major_err = self.DecodeFloat(parsed.major_err)
    minor_err = self.DecodeFloat(parsed.minor_err)
    major_dir = self.DecodeFloat(parsed.major_dir)
    lat_err = self.DecodeFloat(parsed.lat_err)
    lon_err = self.DecodeFloat(parsed.lon_err)
    alt_err = self.DecodeFloat(parsed.alt_err)
    return self.DecGST(
        time, rms_err, major_err, minor_err, major_dir,
        lat_err, lon_err, alt_err
        )
  DECODER_DICT[NmeaParser.ParseGST] = DecodeGST

  @classmethod
  def _MakeRRESat(cls, sat_entry):
    sat = int(sat_entry[0])
    sat_type, num = cls.DecodeSatNum(sat)
    return cls.SatResidual(sat=sat, type=sat_type, num=num,
                           value=float(sat_entry[1]))

  DecRRE = collections.namedtuple(
      'dRRE', 'num_used residuals horiz_err vert_err'
      )
  def DecodeRRE(self, item):
    """Decode xxRRE sentence."""
    parsed = item.parsed
    try:
      num_used = int(parsed.num_used)
      horiz_err = self.DecodeFloat(parsed.horiz_err)
      vert_err = self.DecodeFloat(parsed.vert_err)
      sat_list = tuple(map(self._MakeRRESat, parsed.residuals))
    except ValueError:
      item.decode_error = 'Garbled %s sentence' % item.msgtype
      return None
    return self.DecRRE(num_used=num_used, residuals=sat_list,
                       horiz_err=horiz_err, vert_err=vert_err)
  DECODER_DICT[NmeaParser.ParseRRE] = DecodeRRE

  DecGBS = collections.namedtuple(
      'dGBS',
      'time lat_err lon_err alt_err bad_sat '
      + 'fault_prob range_bias range_bias_sd system signal'
      )
  def DecodeGBS(self, item):  # pylint: disable=too-many-locals
    """Decode a GBS item (GxGBS or similar)."""
    parsed = item.parsed
    time = self.DecodeNmeaTime(parsed.time)
    if not time:
      return None
    lat_err = self.DecodeFloat(parsed.lat_err)
    lon_err = self.DecodeFloat(parsed.lon_err)
    alt_err = self.DecodeFloat(parsed.alt_err)
    bad_sat = self.DecodeInt(parsed.bad_sat)
    sat_type, sat_num = self.DecodeSatNum(bad_sat)
    bad_sat_view = (self.SatView(sat=bad_sat, type=sat_type, num=sat_num)
                    if bad_sat else None)
    fault_prob = self.DecodeFloat(parsed.fault_prob)
    range_bias = self.DecodeFloat(parsed.range_bias)
    range_bias_sd = self.DecodeFloat(parsed.range_bias_sd)
    system = self.DecodeInt(parsed.system)
    signal = self.DecodeInt(parsed.signal)
    return self.DecGBS(
        time, lat_err, lon_err, alt_err, bad_sat_view,
        fault_prob, range_bias, range_bias_sd, system, signal
        )
  DECODER_DICT[NmeaParser.ParseGBS] = DecodeGBS


class Extracter(NmeaExtracter):
  """Class for generic NMEA extracter."""


class Parser(NmeaParser):
  """Class for generic NMEA parser."""


class Decoder(NmeaDecoder):
  """Class for generic NMEA decoder."""
