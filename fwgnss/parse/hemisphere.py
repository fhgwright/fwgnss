"""Module for parsing Hemisphere/Geneq NMEA and binary messages."""

#                      Copyright (c) 2019
#                   Frederick H. G. Wright II
#                          fw@fwright.net
#
#        The information in this software is subject to change
#   without notice and should not be construed as a commitment  #
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

# pylint: disable=too-many-lines

from __future__ import absolute_import, print_function, division

import collections
import math

from . import binary
from . import generic
from . import nmea


class Constants(nmea.Constants,  # pylint: disable=too-few-public-methods
                binary.Constants):
  """Class which holds various constant definitions."""


# Hemisphere/Geneq NMEA additions

class NmeaParser(nmea.Parser):
  """Class for Hemisphere NMEA parser (adds vendor sentences)."""
  NMEA_DICT = nmea.Parser.NMEA_DICT

  # pylint: disable=too-few-public-methods

  @classmethod
  def GetParser(cls, msgtype, subtype=None):
    """Get parser for this message type (and possibly subtype)."""
    parser = cls.NMEA_DICT.get(msgtype)
    return parser and parser.ThisParser(subtype) if subtype else parser

  class ParsePSAT(nmea.Parser.ParseItem):
    """Parser for PSAT sentences."""
    PSAT_DICT = {}
    MIN_LENGTH = 2

    @classmethod
    def ThisParser(cls, subtype=None):
      """Obtain subtype-specific parser for this item."""
      return cls.PSAT_DICT.get(subtype)

    @classmethod
    def Parse(cls, item):
      """Parse a PSAT sentence."""
      subtype = item.data[1].upper()
      item.subtype = subtype
      parser = cls.PSAT_DICT.get(subtype)
      item.parser = parser
      if item.length < parser.MIN_LENGTH:
        item.parse_error = 'Truncated %s sentence' % item.msgtype
        return None
      return parser and parser.Parse(item)

    class ParseGBS(nmea.Parser.ParseItem):
      """Parser for PSAT,GBS sentences."""
      PARSED, MIN_LENGTH = nmea.MakeParser(
          'pGBS',
          'time lat_err lon_err alt_err bad_sat fault_prob '
          + 'range_bias range_bias_sd flag system signal'
          )

      @classmethod
      def Parse(cls, item):
        """Parse a PSAT,GBS sentence."""
        return cls.PARSED._make(item.data[2:13])
    PSAT_DICT['GBS'] = ParseGBS
  NMEA_DICT['PSAT'] = ParsePSAT

  class ParseRD1(nmea.Parser.ParseItem):
    """Parser for RD1 sentences."""
    PARSED, MIN_LENGTH = nmea.MakeParser(
        'RD1',
        'second week freq dsplock ber2 agc dds doppler '
        + 'dspstat armstat diffstat navcon'
        )

    @classmethod
    def Parse(cls, item):
      """Parse an RD1 sentence."""
      return cls.PARSED._make(item.data[1:13])
  NMEA_DICT['RD1'] = ParseRD1

nmea.Nmea.PARSE_CLASS = NmeaParser


class NmeaDecoder(nmea.Decoder):
  """Hemisphere/Geneq added NMEA sentence decoder."""
  DECODER_DICT = nmea.Decoder.DECODER_DICT

  DecGBS = collections.namedtuple(
      'dGBS',
      'time lat_err lon_err alt_err bad_sat '
      + 'fault_prob range_bias range_bias_sd system signal'
      )
  def DecodePSAT_GBS(self,  # pylint: disable=too-many-locals,invalid-name
                     item):
    """Decode a PSAT,GBS item."""
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
  DECODER_DICT[NmeaParser.ParsePSAT.ParseGBS] = DecodePSAT_GBS

  GBS_FLAG_DECODE = {'0': 'Good', '1': 'Warning', '2': 'Bad or fault'}

  DecRD1 = collections.namedtuple(
      'dRD1',
      'dtime freq dspstat armstat diffstat navcon'
      )
  def DecodeRD1(self, item):
    """Decode an RD1 item."""
    parsed = item.parsed
    week = self.DecodeInt(parsed.week)
    second = self.DecodeInt(parsed.second)
    dtime = self.DecodeGPSTime(week, second, store=False)
    freq = self.DecodeFloat(parsed.freq)
    dspstat = self.DecodeInt(parsed.dspstat, 16)
    armstat = self.DecodeInt(parsed.armstat, 16)
    diffstat = self.DecodeInt(parsed.diffstat)
    navcon = self.DecodeInt(parsed.navcon, 16)
    return self.DecRD1(dtime, freq, dspstat, armstat, diffstat, navcon)
  DECODER_DICT[NmeaParser.ParseRD1] = DecodeRD1

  RD1_DSPSTAT_BITS = [
      'Carrier lock',
      'BER OK (Viterbi lock) (yellow LED 2)',
      'L-Band:DSP got lock and has stable freq; WAAS: Frame sync2',
      'Frame sync1',
      'Track mode (same as carrier lock)',
      ]

  RD1_ARMSTAT_BITS = [
      'GPS lock (yellow LED 1)',
      'DGPS valid data',
      'ARM has lock',
      'Diff and GPS (flashing green LED 3)',
      'GPS solution is good (solid green LED 3)',
      'ARM controls yellow LED 2',
      'ARM command for yellow LED 2',
      ]

  RD1_NAVCON_FIELDS = [
      'satellites with valid tracking',
      'satellites with ephemeris received',
      'healthy satellites',
      'usable satellites (tracked, w./ephemeris, healthy, and above mask)',
      'satellites above elevation mask',
      'satellites with differential correction available',
      'satellites with differential correction NOT available',
      ]


# Hemisphere command responses

class Response(generic.TextItem):
  """Response item from extracter."""
  PREFIX_IN = b'$>'
  PREFIX_LEN = len(PREFIX_IN)
  MIN_LEN = PREFIX_LEN + 1

  PREFIX = '$>'
  EOL = '\n'
  SUMMARY_PAT = PREFIX + '%s'
  CONTENTS_PAT = SUMMARY_PAT + EOL

  __slots__ = ()

  def Contents(self):
    return self.CONTENTS_PAT % self.data

  def Summary(self, full=False):
    return self.SUMMARY_PAT % self.data

  def LogText(self):
    return self.data


class ResponseExtracter(generic.Extracter):
  """Class for Hemisphere response extracter."""
  def __new__(cls, infile=None):
    self = super(ResponseExtracter, cls).__new__(cls, infile)
    self.AddExtracter(ResponseExtracter, 'ExtractResponse')
    return self

  def ExtractResponse(self):
    """Extract a response item from the input stream."""
    # Valid line must start with response prefix
    if not self.line.startswith(Response.PREFIX_IN):
      return None, 0
    length, endlen = self.GetEOL()
    if not endlen:
      return None, 0  # Discard unterminated line
    resp = self.GetText(self.line[Response.PREFIX_LEN:length])
    return Response(resp), length + endlen


# Hemisphere/Geneq binary messages

ENDIANNESS = 'little'
ENDIAN_PREFIX = binary.ENDIAN_PREFIXES[ENDIANNESS]


def _Checksum(data):
  return sum(bytearray(data))


class Message(binary.Message):
  """Generic binary message item from extracter."""

  __slots__ = ()

  def Contents(self):
    """Get full message content."""
    if len(self.data) != self.length:
      raise ValueError
    extracter = BinaryExtracter
    checksum = _Checksum(self.data)
    header = extracter.HEADER.pack(extracter.SYNC, self.msgtype, self.length)
    trailer = extracter.TRAILER.pack(checksum, extracter.END)
    return b''.join([header, self.data, trailer])

  def Summary(self, full=False):
    """Get message summary text."""
    if len(self.data) != self.length:
      raise ValueError
    extracter = BinaryExtracter
    parser = self.parser
    if parser:
      return extracter.SUMMARY_DESC_PAT % (self.msgtype, self.length,
                                           parser.DESCRIPTION)
    return extracter.SUMMARY_PAT % (self.msgtype, self.length)


def MakeStruct(pat_list):
  """Create a Hemisphere binary Struct object, from a pattern list."""
  return binary.MakeStruct(ENDIAN_PREFIX, pat_list)


class BinaryExtracter(binary.Extracter):
  """Hemisphere/Geneq binary message extracter."""
  ENDIANNESS = ENDIANNESS
  ENDIAN_PREFIX = ENDIAN_PREFIX
  HEADER = MakeStruct(['4s H H'])
  TRAILER = MakeStruct(['H 2s'])
  HDR_SIZE = HEADER.size
  TRL_SIZE = TRAILER.size
  OVERHEAD = HDR_SIZE + TRL_SIZE
  SYNC = b'$BIN'
  END = b'\r\n'
  LOG_PAT = 'Bin%d(%d)'
  SUMMARY_PAT = '$' + LOG_PAT
  SUMMARY_DESC_PAT = SUMMARY_PAT + ': %s'

  def __new__(cls, infile=None):
    self = super(BinaryExtracter, cls).__new__(cls, infile)
    self.AddExtracter(BinaryExtracter, 'ExtractHemisphere')
    self.parse_map['HEMISPHERE'] = Message.PARSE_CLASS
    return self

  def ExtractHemisphere(self):
    """Extract a Hemisphere binary item from the input stream."""
    if not self.line.startswith(self.SYNC):
      return None, 0
    # Binary message may have embedded apparent EOLs
    while True:
      try:
        _, msgtype, length = self.HEADER.unpack(self.line[:self.HDR_SIZE])
      # Just in case header contains apparent EOL
      except binary.StructError:
        if not self.GetLine():
          return None, 0
        continue
      needed = length + self.OVERHEAD - len(self.line)
      if needed > 0:
        if not self.GetLine(needed):
          return None, 0
        continue
      break
    if needed < 0:  # If too much data (improperly terminated)
      return None, 0
    body = self.line[self.HDR_SIZE:-self.TRL_SIZE]
    checksum, end = self.TRAILER.unpack(self.line[-self.TRL_SIZE:])
    actual_checksum = _Checksum(body)
    if actual_checksum != checksum or end != self.END:
      return None, 0
    consumed = length + self.OVERHEAD
    return Message(data=body, length=length, msgtype=msgtype), consumed

# Need a global handle on this while defining the class
struct_dict = {}  # pylint: disable=invalid-name


def MakeParser(name, pattern):
  """Create a Hemisphere binary parser."""
  return binary.MakeParser(name, ENDIAN_PREFIX, struct_dict, pattern)


def DefineParser(name, pattern):
  """Define a Hemisphere binary parser."""
  binary.DefineParser(name, ENDIAN_PREFIX, struct_dict, pattern)


class BinaryParser(binary.Parser):
  """Hemisphere/Geneq binary message parser."""
  MESSAGE_DICT = {}
  STRUCT_DICT = struct_dict

  # pylint: disable=too-few-public-methods

  @classmethod
  def GetParser(cls, msgtype, subtype=None):
    return cls.MESSAGE_DICT.get(msgtype)

  class MessageParser(binary.Parser.MessageParser):
    """Base class for message-specific parsers."""

  DefineParser(
      'SChannelData',
      'Channel:B SV:B Status:B LastSubframe:B '
      + 'EphmvFlag:B EphmHealth:B AlmVFlag:B AlmHealth:B '
      + 'Elev:b Azimuth:B URA:B Spare:B '
      + 'CliForSNR:H DiffCorr:h PosResid:h VelResid:h '
      + 'DoppHZ:h NCOHz:h'
      )

  DefineParser(
      'SGLONASSChanData',
      'SV:B Alm_Ephm_Flags:B Status_L1:B Status_L2:B '
      + 'Elev:b Azimuth:B LastMessage:B Slip01:B '
      + 'CliForSNR_L1:H CliForSNR_L2:H DiffCorr_L1:h DoppHz:h '
      + 'NCOHz_L1:h NCOHz_L2:h PosResid_1:h PosResid_2:h'
      )

  DefineParser(
      'SSVAlmanData',
      'DoppHz:h CountUpdate:B Svindex:B '
      + 'AlmVFlag:B AlmHealth:B Elev:b Azimuth:B'
      )

  DefineParser(
      'SGLONASS_String',
      'X85Bits:L*3'
      )

  DefineParser(
      'SObservations',
      #'UNICS_TT_SNR_PN:L UIDoppler_FL:L PseudoRange:d Phase:d'
      'PRN:B SNR:B PTT:B CSC:B UIDoppler_FL:l PseudoRange:d Phase:d'
      )

  DefineParser(
      'SObsPacket',
      #'CS_TT_W3_SNR:L P7_Doppler_FL:L CodeAndPhase:L'
      'CS_SNR:H PTT:B CSC:B P7_Doppler_FL:L CodeAndPhase:L'
      )

  DefineParser(
      'SChannelL2Data',
      'Channel:B SV:B L2CX:B L1CX:B '
      + 'CliForSNRL2P:H CliForSNRL1P:H C1_L1:h P2_C1:h '
      + 'P2_L1:h L2_L1:h P2_P1:h NCOHz:h'
      )

  class Bin1(MessageParser):
    """Parser for Bin1 message."""
    DESCRIPTION = 'GPS position message (position and velocity data)'
    PARSER = MakeParser(
        'pBin1',
        'AgeOfDiff:B NumOfSats:B GPSWeek:H GPSTimeOfWeek:d '
        + 'Latitude:d Longitude:d Height:f VNorth:f VEast:f Vup:f '
        + 'StdDevResid:f NavMode:H ExtendedAgeOfDiff:H'
        )
  MESSAGE_DICT[1] = Bin1

  class Bin2(MessageParser):
    """Parser for Bin2 message."""
    DESCRIPTION = 'GPS DOPs (Dilution of Precision)'
    PARSER = MakeParser(
        'pBin2',
        'MaskSatsTracked:L MaskSatsUsed:L GpsUtcDiff:H '
        + 'HDOPTimes10:H VDOPTimes10:H WAASMask:H'
        )
  MESSAGE_DICT[2] = Bin2

  class Bin62(MessageParser):
    """Parser for Bin62 message."""
    DESCRIPTION = 'GLONASS almanac information'
    PARSER = MakeParser(
        'pBin62',
        'SV:B Ktag_ch:B Spare1:H '
        + 'Strings:SGLONASS_String*3'
        )
  MESSAGE_DICT[62] = Bin62

  class Bin65(MessageParser):
    """Parser for Bin65 message."""
    DESCRIPTION = 'GLONASS ephemeris information'
    PARSER = MakeParser(
        'pBin65',
        'SV:B Ktag:B Spare1:H TimeReceivedInSeconds:L '
        + 'Strings:SGLONASS_String*5'
        )
  MESSAGE_DICT[65] = Bin65

  class Bin66(MessageParser):
    """Parser for Bin66 message."""
    DESCRIPTION = 'GLONASS L1/L2 code and carrier phase information'
    PARSER = MakeParser(
        'pBin66',
        'Tow:d Week:H Spare1:H Spare2:L '
        + 'L1Obs:SObsPacket*12 L2Obs:SObsPacket*12 '
        + 'L1CodeMSBsSlot:L*12'
        )
  MESSAGE_DICT[66] = Bin66

  class Bin69(MessageParser):
    """Parser for Bin69 message."""
    DESCRIPTION = 'GLONASS L1/L2 diagnostic information'
    PARSER = MakeParser(
        'pBin69',
        'SecOfWeek:l L1usedNavMask:H L2usedNavMask:H '
        + 'ChannelData:SGLONASSChanData*12 '
        + 'Week:H Spare01:B Spare02:B'
        )
  MESSAGE_DICT[69] = Bin69

  class Bin76(MessageParser):
    """Parser for Bin76 message."""
    DESCRIPTION = 'GPS L1/L2 code and carrier phase information'
    PARSER = MakeParser(
        'pBin76',
        'TOW:d Week:H Spare1:H Spare2:L '
        + 'L2PObs:SObsPacket*12 L1CAObs:SObsPacket*15 '
        + 'L1CACodeMSBsPRN:L*15 L1PCode:L*12'
        )
  MESSAGE_DICT[76] = Bin76

  class Bin80(MessageParser):
    """Parser for Bin80 message."""
    DESCRIPTION = 'SBAS data frame information'
    PARSER = MakeParser(
        'pBin80',
        'PRN:H Spare:H MsgSecOfWeek:L WaasMsg:L*8'
        )
  MESSAGE_DICT[80] = Bin80

  class Bin89(MessageParser):
    """Parser for Bin89 message."""
    DESCRIPTION = 'SBAS satellite tracking information'
    PARSER = MakeParser(
        'pBin89',
        'GPSSecOfWeek:l MaskSBASTracked:B MaskSBASUSED:B Spare:H '
        + 'ChannelData:SChannelData*3'
        )
  MESSAGE_DICT[89] = Bin89

  class Bin93(MessageParser):
    """Parser for Bin93 message."""
    DESCRIPTION = 'SBAS ephemeris information'
    PARSER = MakeParser(
        'pBin93',
        #'SV:H Spare:H TOWSecOfWeek:L IODE:H URA:H TO:l '
        'SV:B Flags:B Spare:H TOWSecOfWeek:L IODE:H URA:H TO:l '
        + 'XG:l YG:l ZG:l XGDot:l YGDot:l ZGDot:l '
        + 'XGDotDot:l YGDotDot:l ZGDotDot:l Gf0:H Gf0Dot:H'
        )
  MESSAGE_DICT[93] = Bin93

  class Bin94(MessageParser):
    """Parser for Bin94 message."""
    DESCRIPTION = 'Ionospheric and UTC conversion parameters'
    PARSER = MakeParser(
        'pBin94',
        'a0:d a1:d a2:d a3:d b0:d b1:d b2:d b3:d A0:d A1:d '
        + 'tot:L wnt:H wnisf:H dn:H dtis:h dtisf:h Spare:H'
        )
  MESSAGE_DICT[94] = Bin94

  class Bin95(MessageParser):
    """Parser for Bin95 message."""
    DESCRIPTION = 'GPS ephemeris information'
    PARSER = MakeParser(
        'pBin95',
        'SV:H Spare1:H SecOfWeek:L '
        + 'SF1words:L*10 SF2words:L*10 SF3words:L*10'
        )
  MESSAGE_DICT[95] = Bin95

  class Bin96(MessageParser):
    """Parser for Bin96 message."""
    DESCRIPTION = 'GPS L1 code and carrier phase information'
    PARSER = MakeParser(
        'pBin96',
        'Spare1:H Week:H TOW:d Obvs:SObservations*12'
        )
  MESSAGE_DICT[96] = Bin96

  class Bin97(MessageParser):
    """Parser for Bin97 message."""
    DESCRIPTION = 'Processor statistics'
    PARSER = MakeParser(
        'pBin97',
        'CPUFactor:L '
        + 'MissedSubFrame:H MaxSubFramePnd:H MissedAccum:H MissedMeas:H '
        + 'Spare1:L Spare2:L Spare3:L Spare4:H Spare5:H'
        )
  MESSAGE_DICT[97] = Bin97

  class Bin98(MessageParser):
    """Parser for Bin98 message."""
    DESCRIPTION = 'GPS satellite and almanac information'
    PARSER = MakeParser(
        'pBin98',
        'AlmanData:SSVAlmanData*8 LastAlman:B IonoUTCVFlag:B Spare:H'
        )
  MESSAGE_DICT[98] = Bin98

  class Bin99(MessageParser):
    """Parser for Bin99 message."""
    DESCRIPTION = 'GPS L1 diagnostic information'
    PARSER = MakeParser(
        'pBin99',
        'NavMode:B UTCTimeDiff:B GPSWeek:H GPSTimeOfWeek:d '
        + 'sChannelData:SChannelData*12 ClockErrAtL1:h Spare:H'
        )
  MESSAGE_DICT[99] = Bin99

  class Bin100(MessageParser):
    """Parser for Bin100 message."""
    DESCRIPTION = 'GPS L2 diagnostic information'
    PARSER = MakeParser(
        'pBin100',
        'NavMode:B UTCTimeDiff:b GPSWeek:H MaskSatsUsedL2P:L '
        + ' GPSTimeOfWeek:d MaskSatsUsedL1P:L '
        + 'sChannelData:SChannelL2Data*12'
        )
  MESSAGE_DICT[100] = Bin100

Message.PARSE_CLASS = BinaryParser

del struct_dict


class BinaryDecoder(binary.Decoder):
  """Hemisphere/Geneq binary message decoder."""
  DECODER_DICT = binary.Decoder.DECODER_DICT

  CN0_OFFSET = 30  # Offset between binary SNR values and dBHz values
  MAX_TRACK_TIME = 25.5  # Maximum reported phase track time

  SIGNAL_SNR_MULT = {
      Constants.SIGNAL_L1CA: 0.1024,
      Constants.SIGNAL_L1P: 0.1164,
      Constants.SIGNAL_L2P: 0.1164,
      Constants.SIGNAL_G1: 0.1024,  # Just a guess
      Constants.SIGNAL_G2: 0.1024,  # Ditto
      }

  def __init__(self):
    super(BinaryDecoder, self).__init__()
    self.knum_dict = {}
    self.g1_wavelengths = {}
    self.g2_wavelengths = {}
    self.no_reconcile_g1_g2 = False

  def _SetKnum(self, slot, knum):
    self.knum_dict[slot] = knum
    self.g1_wavelengths[slot] = Constants.GLO_L1_WAVELENGTHS[knum]
    self.g2_wavelengths[slot] = Constants.GLO_L2_WAVELENGTHS[knum]

  @staticmethod
  def _ItemsByMask(value, sats=tuple(range(1, 33))):
    sat_list = []
    sat_bit = 1
    for sat_num in sats:
      if value & sat_bit:
        sat_list.append(sat_num)
      sat_bit <<= 1
    return tuple(sat_list)

  SChannelData = BinaryParser.STRUCT_DICT['SChannelData'][0]
  DecSCD = collections.namedtuple(
      'dSChanData',
      ' '.join(SChannelData._fields)
      .replace('CliForSNR', 'SNR')
      )
  @classmethod
  def _DecodeSChannelData(cls, scd_list):
    result = []
    for scd in scd_list:
      if not scd.SV:
        continue
      azim = scd.Azimuth * 2
      cli = scd.CliForSNR
      snr = (10.0 * math.log10(4096.0 * cli / 80000.0) + cls.CN0_OFFSET
             if cli else None)
      diffcorr = scd.DiffCorr / 100.0
      posresid = scd.PosResid / 10.0
      velresid = scd.VelResid / 10.0
      mod_scd = scd._replace(Azimuth=azim, CliForSNR=snr, DiffCorr=diffcorr,
                             PosResid=posresid, VelResid=velresid)
      result.append(cls.DecSCD._make(mod_scd))
    return tuple(result)

  SGLONASSChanData = BinaryParser.STRUCT_DICT['SGLONASSChanData'][0]
  DecSGloCD = collections.namedtuple(
      'dSGloChanData',
      ' '.join(SGLONASSChanData._fields)
      #.replace('CliForSNR_L1', 'SNR_L1')
      #.replace('CliForSNR_L2', 'SNR_L2')
      + ' knum_flag slot knum chan l1_used l2_used'
      )
  def _DecodeSGLONASSChanData(self,  # pylint: disable=too-many-locals
                              scd_list, l1_used_mask, l2_used_mask):
    result = []
    chan = -1
    for scd in scd_list:
      chan += 1
      slot_val = scd.SV
      slot = slot_val & 0x7F
      if not slot:
        continue
      knum_flag = slot_val >> 7 & 1 != 0
      if knum_flag:
        knum = slot - 8
        slot = None
      else:
        knum = self.knum_dict.get(slot)
      azim = scd.Azimuth * 2
      diffcorr = scd.DiffCorr_L1 / 100.0
      posresid1 = scd.PosResid_1 / 1000.0
      posresid2 = scd.PosResid_2 / 1000.0
      l1_used = l1_used_mask & 1 << chan != 0
      l2_used = l2_used_mask & 1 << chan != 0
      mod_scd = scd._replace(Azimuth=azim, DiffCorr_L1=diffcorr,
                             PosResid_1=posresid1, PosResid_2=posresid2)
      result.append(self.DecSGloCD._make(list(mod_scd)
                                         + [knum_flag, slot, knum,
                                            chan, l1_used, l2_used]))
    return tuple(result)

  SChannelL2Data = BinaryParser.STRUCT_DICT['SChannelL2Data'][0]
  DecSCL2D = collections.namedtuple(
      'dSChanL2Data',
      ' '.join(SChannelL2Data._fields)
      #.replace('CliForSNRL2P', 'SNR_L2P')
      #.replace('CliForSNRL1P', 'SNR_L1P')
      )
  @classmethod
  def _DecodeSChannelL2Data(cls, scd_list):
    result = []
    for scd in scd_list:
      if not scd.SV or (scd.L1CX & 0x20 and scd.L2CX & 0x20):
        continue
      result.append(cls.DecSCL2D(
          Channel=scd.Channel, SV=scd.SV, L2CX=scd.L2CX, L1CX=scd.L1CX,
          CliForSNRL2P=scd.CliForSNRL2P, CliForSNRL1P=scd.CliForSNRL1P,
          C1_L1=scd.C1_L1 / 100.0, P2_C1=scd.P2_C1 / 100.0,
          P2_L1=scd.P2_L1 / 100.0, L2_L1=scd.L2_L1 / 100.0,
          P2_P1=scd.P2_P1 / 100.0, NCOHz=scd.NCOHz
          ))
    return tuple(result)

  @classmethod
  def _DecodeSObservations(cls, sobs_list):  # pylint: disable=too-many-locals
    result = []
    idx = -1
    for sobs in sobs_list:
      idx += 1
      sat_id, snr_val = sobs.PRN, sobs.SNR
      if not sat_id or not snr_val:
        continue
      snr = 10.0 * math.log10(0.8192 * snr_val) + cls.CN0_OFFSET
      dopp_val = sobs.UIDoppler_FL
      if dopp_val & (1 << 1):
        track_time = cls.MAX_TRACK_TIME
        track_max = True
      else:
        track_time = sobs.PTT / 10.0
        track_max = False
      slip_counter = sobs.CSC
      slip_warn = 0
      pseudorange = sobs.PseudoRange
      wavelength = Constants.GPS_L1_WAVELENGTH
      if dopp_val & (1 << 0):
        phase = sobs.Phase / wavelength
      else:
        phase = 0.0  # Assumes real phase values are nonzero pseudorange-like
      doppler = (dopp_val >> 4) / 4096.0 / Constants.GPS_L1_WAVELENGTH
      doppler = -doppler  # correct inverted Doppler sense
      sig_obs = (cls.SigObservation(
          signal=Constants.SIGNAL_L1CA,
          snr=snr, track_time=track_time, track_max=track_max,
          slip_counter=slip_counter, slip_warn=slip_warn,
          wavelength=wavelength,
          pseudorange=pseudorange, doppler=doppler, phase=phase
          ),)
      result.append(cls.SatObservation(
          system=Constants.SYSTEM_ID_GPS,
          sat_id=sat_id, knum=None, idx=idx, spare=None, sig_obs=sig_obs
          ))
    return tuple(result)

  @staticmethod
  def _ComputePseudorange(pr_high, pr_low, pr_ref_low):
    pr_adj = (pr_low - pr_ref_low + 0x8000 & 0xFFFF) - 0x8000
    pseudorange = (pr_ref_low + pr_adj) / 256.0 + pr_high * 256.0
    return pseudorange

  @classmethod
  def _ComputeSNR(cls, signal, snr_val):
    return (10.0 * math.log10(cls.SIGNAL_SNR_MULT[signal] * snr_val)
            + cls.CN0_OFFSET)

  @classmethod
  def _DecodeSobsPacket(  # pylint: disable=too-many-locals,too-many-arguments
      cls, signal, sobs, pr_hi, pr_ref_low=None, wavelength=None
      ):
    cs_snr = sobs.CS_SNR
    snr_val = cs_snr & 0xFFF
    if not snr_val:
      return None
    snr = cls._ComputeSNR(signal, snr_val)
    if cs_snr & (1 << 15):
      track_time = cls.MAX_TRACK_TIME
      track_max = True
    else:
      track_time = sobs.PTT / 10.0
      track_max = False
    slip_counter = sobs.CSC
    slip_warn = (cs_snr >> 12) & 0x7
    code_and_phase = sobs.CodeAndPhase
    pr_low = code_and_phase & 0xFFFF
    if pr_ref_low is None:
      pr_ref_low = pr_low
    pseudorange = cls._ComputePseudorange(pr_hi, pr_low, pr_ref_low)
    dopp_and_phase = sobs.P7_Doppler_FL
    dopp_val = (dopp_and_phase >> 1) & 0x7FFFFF
    if dopp_and_phase & (1 << 24):
      dopp_val = -dopp_val
    doppler = dopp_val / 512.0
    doppler = -doppler  # correct inverted Doppler sense
    if dopp_and_phase & (1 << 0):
      phase_val = (((dopp_and_phase >> (25 - 16)) & (0x7F << 16))
                   + ((code_and_phase >> 16) & 0xFFFF))
      phase_int, phase_frac = divmod(phase_val, 1024)
      if wavelength:
        phase_ref = int(pseudorange / wavelength)
        phase_adj = ((phase_int - phase_ref + 0x1000) & 0x1FFF) - 0x1000
        phase_int = phase_ref + phase_adj
      phase = phase_int + phase_frac / 1024.0
    else:
      phase = 0.0
    return cls.SigObservation(
        signal=signal,
        snr=snr, track_time=track_time, track_max=track_max,
        slip_counter=slip_counter, slip_warn=slip_warn,
        wavelength=wavelength,
        pseudorange=pseudorange, doppler=doppler, phase=phase
        )

  @classmethod
  def _DecodeL1P(cls,  # pylint: disable=too-many-arguments
                 signal, obs_val, pr_hi, pr_ref_low, l1ca_obs):
    snr_val = (obs_val >> 16) & 0xFFF
    if not snr_val:
      return []
    snr = cls._ComputeSNR(signal, snr_val)
    pr_low = obs_val & 0xFFFF
    pseudorange = cls._ComputePseudorange(pr_hi, pr_low, pr_ref_low)
    return l1ca_obs._replace(signal=signal, snr=snr, pseudorange=pseudorange)

  DecBin1 = collections.namedtuple('dBin1', 'dtime speed track diff_age')
  def DecodeBin1(self, item):
    """Decode Bin1 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.GPSWeek, parsed.GPSTimeOfWeek)
    vel_n, vel_e = parsed.VNorth, parsed.VEast
    speed = math.sqrt(vel_n ** 2 + vel_e ** 2)
    track = math.atan2(vel_e, vel_n) * 180.0 / math.pi
    if track < 0.0:
      track += 360.0
    diff_age = parsed.ExtendedAgeOfDiff or parsed.AgeOfDiff or None
    return self.DecBin1(dtime, speed, track, diff_age)
  DECODER_DICT[BinaryParser.Bin1] = DecodeBin1

  BIN1_NAVMODE_DECODE = [
      'No Fix',
      'Fix 2D no diff',
      'Fix 3D no diff',
      'Fix 2D with diff',
      'Fix 3D with diff',
      'RTK float',
      'RTK integer fixed',
      ]

  DecBin2 = collections.namedtuple(
      'dBin2',
      'tracked used hdop vdop waas_tracked waas_used'
      )
  def DecodeBin2(self, item):
    """Decode Bin2 message."""
    parsed = item.parsed
    tracked = self._ItemsByMask(parsed.MaskSatsTracked)
    used = self._ItemsByMask(parsed.MaskSatsUsed)
    hdop = parsed.HDOPTimes10 / 10.0
    vdop = parsed.VDOPTimes10 / 10.0
    waas_mask = parsed.WAASMask
    sats = [((waas_mask >> bit) & 0x1F) + 120 for bit in [5, 10]]
    waas_tracked = self._ItemsByMask((waas_mask >> 0) & 3, sats)
    waas_used = self._ItemsByMask((waas_mask >> 2) & 3, sats)
    return self.DecBin2(tracked, used, hdop, vdop, waas_tracked, waas_used)
  DECODER_DICT[BinaryParser.Bin2] = DecodeBin2

  DecBin62 = collections.namedtuple('dBin62', 'knum')
  def DecodeBin62(self, item):
    """Decode Bin62 message."""
    parsed = item.parsed
    # K number (possibly offset) appears in bits 14:10 of odd almanac string
    knum = ((parsed.Strings[1].X85Bits[2] >> 20) + 7 & 0x1F) - 7
    self._SetKnum(parsed.SV, knum)
    return self.DecBin62(knum)
  DECODER_DICT[BinaryParser.Bin62] = DecodeBin62

  BIN62_STRINGS = ['Almanac even', 'Almanac odd ', 'String 5    ']

  GLONASS_STRING_RPAD = 3 * 32 - (85 - 8)

  SGLONASS_VALIDITY_BITS = [
      'Ephemeris available but timed out',
      'Ephemeris valid',
      'Ephemeris health OK',
      'unused',
      'Almanac available',
      'Almanac health OK',
      'unused',
      'Satellite doesn\'t exist',
      ]

  SCHANNEL_STATUS_DECODE = [
      'code lock',
      'carrier lock',
      'bit lock',
      'frame sync',
      'frame sync and new epoch',
      'channel reset',
      'phase lock',
      '(spare)',
      ]

  SCHANNEL_VALIDITY_DECODE = [
      'not logged',
      'invalid',
      'valid',
      'has data (not yet validated)',
      ]

  DecBin65 = collections.namedtuple('dBin65', 'knum')
  def DecodeBin65(self, item):
    """Decode Bin65 message."""
    parsed = item.parsed
    knum = parsed.Ktag - 8
    self._SetKnum(parsed.SV, knum)
    return self.DecBin65(knum)
  DECODER_DICT[BinaryParser.Bin65] = DecodeBin65

  BIN65_STRINGS = ['String %d' % (i + 1) for i in range(5)]

  def DecodeBin66(self, item):  # pylint: disable=too-many-locals
    """Decode Bin66 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.Week, parsed.Tow, store=False)
    msb_slots = parsed.L1CodeMSBsSlot
    l1_obs, l2_obs = parsed.L1Obs, parsed.L2Obs
    sat_obs_list = []
    for idx, msb_slot in enumerate(msb_slots):
      slot = msb_slot & 0xFF
      if not slot:
        continue
      knum = self.knum_dict.get(slot)
      l1_wave = self.g1_wavelengths.get(slot)
      l2_wave = self.g2_wavelengths.get(slot)
      spare = (msb_slot >> 8) & 0x1F
      pr_high = (msb_slot >> 13) & 0x7FFFF
      sig_obs_list = []
      pr_ref_low = None
      obs = l1_obs[idx]
      obs_entry = self._DecodeSobsPacket(Constants.SIGNAL_G1, obs,
                                         pr_high, wavelength=l1_wave)
      if obs_entry:
        sig_obs_list.append(obs_entry)
        if not self.no_reconcile_g1_g2:
          pr_ref_low = obs.CodeAndPhase & 0xFFFF
      obs_entry = self._DecodeSobsPacket(Constants.SIGNAL_G2, l2_obs[idx],
                                         pr_high, pr_ref_low,
                                         wavelength=l2_wave)
      if obs_entry:
        sig_obs_list.append(obs_entry)
      if sig_obs_list:
        sat_obs_list.append(self.SatObservation(
            system=Constants.SYSTEM_ID_GLONASS,
            sat_id=slot, knum=knum, idx=idx, spare=spare,
            sig_obs=tuple(sig_obs_list)
            ))
    return self.ObservationSet(dtime=dtime, sat_obs=tuple(sat_obs_list))
  DECODER_DICT[BinaryParser.Bin66] = DecodeBin66

  DecBin69 = collections.namedtuple(
      'dBin69',
      'dtime num_chans l1_used l2_used data'
      )
  def DecodeBin69(self, item):
    """Decode Bin69 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.Week, parsed.SecOfWeek)
    num_chans = len(parsed.ChannelData)
    chans = tuple(range(num_chans))
    l1_used = self._ItemsByMask(parsed.L1usedNavMask, chans)
    l2_used = self._ItemsByMask(parsed.L2usedNavMask, chans)
    data = self._DecodeSGLONASSChanData(parsed.ChannelData,
                                        parsed.L1usedNavMask,
                                        parsed.L2usedNavMask)
    return self.DecBin69(dtime, num_chans, l1_used, l2_used, data)
  DECODER_DICT[BinaryParser.Bin69] = DecodeBin69

  def DecodeBin76(self, item):  # pylint: disable=too-many-locals
    """Decode Bin76 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.Week, parsed.TOW, store=False)
    msb_prns = parsed.L1CACodeMSBsPRN
    l1p_array, l2p_array = parsed.L1PCode, parsed.L2PObs
    sat_obs_list = []
    for idx, msb_prn in enumerate(msb_prns):
      prn = msb_prn & 0xFF
      if not prn:
        continue
      obs = parsed.L1CAObs[idx]
      spare = (msb_prn >> 8) & 0x1F
      pr_high = (msb_prn >> 13) & 0x7FFFF
      sig_obs_list = []
      l1ca_entry = self._DecodeSobsPacket(
          Constants.SIGNAL_L1CA, obs, pr_high,
          wavelength=Constants.GPS_L1_WAVELENGTH
          )
      if l1ca_entry:
        sig_obs_list.append(l1ca_entry)
      pr_ref_low = obs.CodeAndPhase & 0xFFFF
      if idx < len(l1p_array):
        obs = l1p_array[idx]
        obs_entry = self._DecodeL1P(Constants.SIGNAL_L1P,
                                    obs, pr_high, pr_ref_low, l1ca_entry)
        if obs_entry:
          sig_obs_list.append(obs_entry)
      if idx < len(l2p_array):
        obs = l2p_array[idx]
        obs_entry = self._DecodeSobsPacket(
            Constants.SIGNAL_L2P, obs, pr_high, pr_ref_low,
            wavelength=Constants.GPS_L2_WAVELENGTH
            )
        if obs_entry:
          sig_obs_list.append(obs_entry)
      if sig_obs_list:
        sat_obs_list.append(self.SatObservation(
            system=Constants.SYSTEM_ID_GPS,
            sat_id=prn, knum=None, idx=idx, spare=spare,
            sig_obs=tuple(sig_obs_list)
            ))
    return self.ObservationSet(dtime=dtime, sat_obs=tuple(sat_obs_list))
  DECODER_DICT[BinaryParser.Bin76] = DecodeBin76

  DecBin80 = collections.namedtuple('dBin80', 'preamble type crc pad')
  def DecodeBin80(self, item):
    """Decode Bin80 message."""
    parsed = item.parsed
    preamble = (parsed.WaasMsg[0] >> 24) & 0xFF
    msgtype = (parsed.WaasMsg[0] >> 18) & 0x3F
    crc = (parsed.WaasMsg[7] >> (32 * 8 - 250)) & 0xFFFFFF
    pad = parsed.WaasMsg[7] & ((1 << (32 * 8 - 250)) - 1)
    return self.DecBin80(preamble, msgtype, crc, pad)
  DECODER_DICT[BinaryParser.Bin80] = DecodeBin80

  DecBin89 = collections.namedtuple('dBin89', 'sats tracked used data')
  def DecodeBin89(self, item):
    """Decode Bin89 message."""
    parsed = item.parsed
    sats = tuple([scd.SV for scd in parsed.ChannelData])
    tracked = self._ItemsByMask(parsed.MaskSBASTracked, sats)
    used = self._ItemsByMask(parsed.MaskSBASUSED, sats)
    data = self._DecodeSChannelData(parsed.ChannelData)
    return self.DecBin89(sats, tracked, used, data)
  DECODER_DICT[BinaryParser.Bin89] = DecodeBin89

  DecBin93 = collections.namedtuple(
      'dBin93',
      'XG YG ZG XGDot YGDot ZGDot '
      + 'XGDotDot YGDotDot ZGDotDot Gf0 Gf0Dot'
      )
  def DecodeBin93(self, item):
    """Decode Bin93 message."""
    parsed = item.parsed
    return self.DecBin93(
        XG=parsed.XG * .08,
        YG=parsed.YG * .08,
        ZG=parsed.ZG * .4,
        XGDot=parsed.XGDot * .000625,
        YGDot=parsed.YGDot * .000625,
        ZGDot=parsed.ZGDot * .004,
        XGDotDot=parsed.XGDotDot * .0000125,
        YGDotDot=parsed.YGDotDot * .0000125,
        ZGDotDot=parsed.ZGDotDot * .0000625,
        Gf0=parsed.Gf0 / (65536.0 * 32768.0),
        Gf0Dot=parsed.Gf0Dot / (1024.0 ** 4),
        )
  DECODER_DICT[BinaryParser.Bin93] = DecodeBin93

  DecBin94 = collections.namedtuple(
      'dBin94',
      'dtime nleap_dtime alphas betas utcs'
      )
  DecBin94a = collections.namedtuple('dBin94a', 'a0 a1 a2 a3')
  DecBin94b = collections.namedtuple('dBin94b', 'b0 b1 b2 b3')
  DecBin94u = collections.namedtuple('dBin94u', 'A0 A1')
  def DecodeBin94(self, item):
    """Decode Bin94 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.wnt, parsed.tot, store=False)
    week, sec = parsed.wnisf, parsed.dn * Constants.SECONDS_PER_DAY + parsed.dtis
    if sec >= Constants.SECONDS_PER_WEEK:
      week += 1
      sec -= Constants.SECONDS_PER_WEEK
    nleap_dtime = self.DecodeGPSTime(week, sec, store=False)
    alphas = self.DecBin94a(parsed.a0, parsed.a1, parsed.a2, parsed.a3)
    betas = self.DecBin94b(parsed.b0, parsed.b1, parsed.b2, parsed.b3)
    utcs = self.DecBin94u(parsed.A0, parsed.A1)
    return self.DecBin94(dtime, nleap_dtime, alphas, betas, utcs)
  DECODER_DICT[BinaryParser.Bin94] = DecodeBin94

  DecBin95 = collections.namedtuple('dBin95', 'RealSecOfWeek')
  def DecodeBin95(self, item):
    """Decode Bin95 message."""
    parsed = item.parsed
    real_sec_of_week = parsed.SecOfWeek * 6
    return self.DecBin95(real_sec_of_week)
  DECODER_DICT[BinaryParser.Bin95] = DecodeBin95

  def DecodeBin96(self, item):
    """Decode Bin96 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.Week, parsed.TOW, store=False)
    sat_obs = self._DecodeSObservations(parsed.Obvs)
    return self.ObservationSet(dtime=dtime, sat_obs=sat_obs)
  DECODER_DICT[BinaryParser.Bin96] = DecodeBin96

  DecBin97 = collections.namedtuple('dBin97', 'cpu_unused spares')
  DecBin97s = collections.namedtuple(
      'dBin97s',
      'Spare1 Spare2 Spare3 Spare4 Spare5'
      )
  def DecodeBin97(self, item):
    """Decode Bin97 message."""
    parsed = item.parsed
    cpu_unused = parsed.CPUFactor * 450E-6
    spares = self.DecBin97s(parsed.Spare1, parsed.Spare2, parsed.Spare3,
                            parsed.Spare4, parsed.Spare5)
    return self.DecBin97(cpu_unused, spares)
  DECODER_DICT[BinaryParser.Bin97] = DecodeBin97

  SSVAlmanData = BinaryParser.STRUCT_DICT['SSVAlmanData'][0]
  DecSSVA = collections.namedtuple(
      'dSSVA', ' '.join(SSVAlmanData._fields).replace('Svindex', 'SV'))
  def DecodeBin98(self, item):
    """Decode Bin98 message."""
    parsed = item.parsed
    ssva_list = []
    for ssva in parsed.AlmanData:
      svidx = ssva.Svindex + 1
      azim = ssva.Azimuth * 2
      mod_ssva = ssva._replace(Svindex=svidx, Azimuth=azim)
      ssva_list.append(self.DecSSVA._make(mod_ssva))
    return tuple(ssva_list)
  DECODER_DICT[BinaryParser.Bin98] = DecodeBin98

  DecBin99 = collections.namedtuple('dBin99', 'dtime navmode diff data')
  def DecodeBin99(self, item):
    """Decode Bin99 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.GPSWeek, parsed.GPSTimeOfWeek,
                               store=False)
    # Note that the diff bit is the upper bit of the *nibble*, not the byte
    # as stated in the doc.
    navmode = parsed.NavMode & 0x07
    diff = parsed.NavMode & 0x08 != 0
    data = self._DecodeSChannelData(parsed.sChannelData)
    return self.DecBin99(dtime, navmode, diff, data)
  DECODER_DICT[BinaryParser.Bin99] = DecodeBin99

  BIN99_NAVMODE_DECODE = [
      'Time not valid',
      'No Fix',
      'Fix 2D',
      'Fix 3D',
      ]

  DecBin100 = collections.namedtuple(
      'dBin100',
      'dtime navmode diff l1p_used l2p_used data'
      )
  def DecodeBin100(self, item):
    """Decode Bin100 message."""
    parsed = item.parsed
    dtime = self.DecodeGPSTime(parsed.GPSWeek, parsed.GPSTimeOfWeek,
                               store=False)
    # Note that the diff bit is the upper bit of the *nibble*, not the byte
    # as stated in the doc.
    navmode = parsed.NavMode & 0x07
    diff = parsed.NavMode & 0x08 != 0
    l1p_used = self._ItemsByMask(parsed.MaskSatsUsedL1P)
    l2p_used = self._ItemsByMask(parsed.MaskSatsUsedL2P)
    data = self._DecodeSChannelL2Data(parsed.sChannelData)
    return self.DecBin100(dtime, navmode, diff, l1p_used, l2p_used, data)
  DECODER_DICT[BinaryParser.Bin100] = DecodeBin100


class Extracter(BinaryExtracter, nmea.Extracter, ResponseExtracter):
  """Class for combined extracter."""
  # We put the binary extracter first since the NMEA extracter doesn't
  # immediately reject the '$BIN' prefix.


class Parser(NmeaParser, BinaryParser):
  """Class for combined parser."""


class Decoder(NmeaDecoder, BinaryDecoder):
  """Class for combined decoder."""
