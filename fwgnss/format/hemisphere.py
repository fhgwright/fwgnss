"""Module for formatting Hemisphere/Geneq data into human-friendly form."""

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
from . import nmea
from ..parse import hemisphere

VENDORS = set(['Hemisphere', 'Geneq'])


class NmeaConstants(nmea.Constants):  # pylint: disable=too-few-public-methods
  """Class for various NMEA-related constant definitions."""


class NmeaFormatter(nmea.NmeaFormatter):
  """Class for Hemisphere/Geneq NMEA formatter objects."""
  PARSER = hemisphere.NmeaParser
  DECODER = hemisphere.NmeaDecoder

  FORMATTER_DICT = nmea.NmeaFormatter.FORMATTER_DICT.copy()

  # Pylint seems to be too dumb to realize that the 'decoder' instance
  # variable here will point to an instance of parse_nmea.Decoder, rather
  # than parse_gnss.Decoder, and it complains about various missing members.
  # The only non-obnoxious solution seems to be to disable that error.
  #
  # It should probably be temporarily undisabled after any major changes.
  #
  # pylint: disable=no-member

  def FormatPSAT_GBS(self, item):  # pylint: disable=invalid-name
    """Format a PSAT,GBS sentence."""
    parsed = item.parsed
    # This next item is the only difference from the GxGBS case
    status_list = ['HPR status = %s'
                   % self.DecodeChar(parsed.flag, self.decoder.GBS_FLAG_DECODE)]
    self.FormatGBS(item, extra=status_list)
  FORMATTER_DICT[PARSER.GetParser('PSAT', 'GBS')] = FormatPSAT_GBS

  def FormatRD1(self, item):
    """Format an RD1 sentence."""
    parsed = item.parsed
    decoded = item.decoded
    time_list = ['SBAS status for GPS week/second %s/%s'
                 % (parsed.week, parsed.second)]
    if decoded.dtime:
      time_list.append(' (%s)' % self.GetDateTimeStr(decoded.dtime, 0))
    self.Send(2, ''.join(time_list + [':']))
    self.Send(4, (('Using S-%d on %.2fMHz,'
                   + ' dsplock=%s, BER(2)=%s, AGC=%s, DDS=%s, Doppler=%s')
                  % (decoded.diffstat, decoded.freq, parsed.dsplock,
                     parsed.ber2, parsed.agc, parsed.dds, parsed.doppler)))
    self.DumpBits(6, 'DSP tracking of SBAS status = ',
                  '%.04X', decoded.dspstat,
                  self.decoder.RD1_DSPSTAT_BITS, group=2)
    self.DumpBits(6, 'ARM GPS solution status = ',
                  '%.04X', decoded.armstat,
                  self.decoder.RD1_ARMSTAT_BITS, group=2)
    self.DumpNibbles(4, 'NAVCON satellite counts = %07X',
                     decoded.navcon, self.decoder.RD1_NAVCON_FIELDS)
  FORMATTER_DICT[PARSER.GetParser('RD1')] = FormatRD1


class HemisphereConstants(  # pylint: disable=too-few-public-methods
    hemisphere.Constants
    ):
  """Class for various Hemisphere-related constant definitions."""


class BinaryFormatter(generic.BinaryFormatter):
  """Class for Hemisphere/Geneq binary formatter objects."""
  EXTRACTER = hemisphere.BinaryExtracter
  PARSER = hemisphere.BinaryParser
  DECODER = hemisphere.BinaryDecoder

  FORMATTER_DICT = generic.BinaryFormatter.FORMATTER_DICT.copy()

  # Pylint seems to be too dumb to realize that the 'decoder' instance
  # variable here will point to an instance of hemisphere.BinaryDecoder,
  # rather than parse_gnss.Decoder, and it complains about various missing
  # members.
  # The only non-obnoxious solution seems to be to disable that error.
  #
  # It should probably be temporarily undisabled after any major changes.
  #
  # pylint: disable=no-member

  def SetFormatLevel(self, level):
    """Set formatter compatibility level."""
    super(BinaryFormatter, self).SetFormatLevel(level)
    if level < self.FMT_UPDATED:
      self.decoder.no_reconcile_g1_g2 = True

  def _DumpObservations(self,  # pylint: disable=too-many-locals
                        indent, obs_data, label='PRN', show_knum=False):
    obs_list = list(obs_data)
    obs_list.sort()
    for sat_obs in obs_list:
      cur_indent = indent
      knum_v = '%+d' % sat_obs.knum if sat_obs.knum is not None else '??'
      knum_str = ' (K= %s)' % knum_v if show_knum else ''
      if self.fmt_level < self.FMT_UPDATED and sat_obs.knum is None:
        knum_str = ''
      for sig_obs in sat_obs.sig_obs:
        if self.fmt_level < self.FMT_UPDATED and not show_knum:
          # Old code used L1CA pseudorange for all, but not for GLONASS
          pseudorange = sat_obs.sig_obs[0].pseudorange
          sig_obs = sig_obs._replace(pseudorange=pseudorange)
        line1 = ['%s %d%s @%d %s: SNR = %.1f dBHz'
                 % (label, sat_obs.sat_id, knum_str, sat_obs.idx,
                    HemisphereConstants.SIGNAL_NAMES[sig_obs.signal],
                    sig_obs.snr)]
        line2 = ['Pseudorange = %.3f m' % sig_obs.pseudorange,
                 'Doppler = %+.3f Hz' % sig_obs.doppler]
        if sig_obs.phase != 0.0:
          max_flag = '>' if sig_obs.track_max else ''
          if self.fmt_level < self.FMT_UPDATED:
            phase_pfx = ''
          else:
            phase_pfx = '' if sig_obs.wavelength else '+'
          line1.append('phase tracked for %s%.1fs'
                       % (max_flag, sig_obs.track_time))
          line2.append('phase = %s%.3f cyc' % (phase_pfx, sig_obs.phase))
        else:
          line1.append('phase not tracked')
        line1.append('cycle slip counter = %d/%d'
                     % (sig_obs.slip_counter, sig_obs.slip_warn))
        self.Send(cur_indent, ', '.join(line1))
        self.Send(cur_indent + 2, ', '.join(line2))
        cur_indent = indent + 1

  def _DumpSChannelData(self, indent, data):
    if self.fmt_level < self.FMT_UPDATED:
      self.DumpBits(indent,
                    'PRN %d on channel %d, last subframe = %d, status = '
                    % (data.SV, data.Channel, data.LastSubframe), '%.02X',
                    data.Status, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    else:
      self.DumpBits(indent,
                    'PRN %d on channel %d, last subframe = %d, status = 0x'
                    % (data.SV, data.Channel, data.LastSubframe), '%.02X',
                    data.Status, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    if data.Status & 0x20:
      return
    out_list = [self._FormatVH('Ephemeris', data.EphmvFlag, data.EphmHealth)]
    out_list.append(self._FormatVH('Almanac', data.AlmVFlag, data.AlmHealth))
    self.Send(indent + 2, '; '.join(out_list))
    out_list = [self._FormatElAz(data.Elev, data.Azimuth)]
    out_list.append('user range error = %d' % data.URA)
    out_list.append('spare = 0x%.02X' % data.Spare)
    self.Send(indent + 2, ', '.join(out_list))
    snr = '%.1f dBHz' % data.SNR if data.SNR else '?'
    self.Send(indent + 2,
              ('SNR = %s, pseudorange diff corr = %.2fm, '
               + 'position residual = %.1fm, velocity residual = %.1f m/s')
              % (snr, data.DiffCorr, data.PosResid, data.VelResid))
    doppler, nco = data.DoppHZ, data.NCOHz
    self.Send(indent + 2,
              ('Expected Doppler offset = %+d Hz, '
               + 'carrier track offset = %+d Hz (delta = %+d Hz)')
              % (doppler, nco, nco - doppler))

  def _FormatVH(self, name, validity, health):
    v_str = self.DecodeEnum(validity, self.decoder.SCHANNEL_VALIDITY_DECODE)
    return '%s validity = %s, health = 0x%.02X' % (name, v_str, health)

  @staticmethod
  def _FormatElAz(elev, azim):
    return 'Elevation = %d, azimuth = %d' % (elev, azim)

  def _DumpSGLONASSChanData(self, indent, data):
    l1_str = ' (used)' if data.l1_used else ''
    l2_str = ' (used)' if data.l2_used else ''
    doppler, nco_l1 = data.DoppHz, data.NCOHz_L1
    l2_status = data.Status_L2
    id_str = 'Knum %+d' % data.knum if data.knum_flag else 'Slot %d' % data.slot
    self.Send(indent, ('%s on channel %d, last message processed = %d'
                       % (id_str, data.chan, data.LastMessage)))
    self.DumpBits(indent + 2, 'G1%s channel status = 0x' % l1_str, '%.02X',
                  data.Status_L1, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    self.DumpBits(indent + 2, 'G2%s channel status = 0x' % l2_str, '%.02X',
                  l2_status, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    prefix = ('Elevation = %d, azimuth = %d, almanac/ephemeris validity = 0x'
              % (data.Elev, data.Azimuth))
    self.DumpBits(indent + 2, prefix, '%.02X', data.Alm_Ephm_Flags,
                  self.decoder.SGLONASS_VALIDITY_BITS, group=4)
    snr_list = ['G1 SNR (cli) = %d' % data.CliForSNR_L1]
    if data.Status_L2:
      snr_list.append('G2 SNR (cli) = %d' % data.CliForSNR_L2)
    snr_list.append('cycle slip (ch1) = %d' % data.Slip01)
    self.Send(indent + 2, ', '.join(snr_list))
    self.Send(indent + 2,
              'Diff corr (G1) = %.2fm, range residuals #1 = %.3fm, #2 = %.3fm'
              % (data.DiffCorr_L1, data.PosResid_1, data.PosResid_2))
    dopp_list = ['Expected G1 Doppler = %+d Hz' % doppler]
    if l2_status:
      dopp_list.append(', carrier track offsets G1 = %+d Hz' % nco_l1)
    else:
      dopp_list.append(', carrier track offset = %+d Hz' % nco_l1)
    if doppler:
      dopp_list.append(' (delta = %+d Hz)' % (nco_l1 - doppler))
    if l2_status:
      dopp_list.append(', G2 = %+d Hz' % data.NCOHz_L2)
    self.Send(indent + 2, ''.join(dopp_list))

  def _DumpSChannelL2Data(self, indent, data):
    self.Send(indent, 'PRN %d on channel %d:' % (data.SV, data.Channel))
    if self.fmt_level < self.FMT_UPDATED:
      self.DumpBits(indent + 4,
                    'L1P SNR = ?, status = ',
                    '%.02X',
                    data.L1CX, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
      self.DumpBits(indent + 4,
                    'L2P SNR = ?, status = ',
                    '%.02X',
                    data.L2CX, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    else:
      self.DumpBits(indent + 4,
                    'L1P SNR (cli) = %d, status = 0x' % data.CliForSNRL1P,
                    '%.02X',
                    data.L1CX, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
      self.DumpBits(indent + 4,
                    'L2P SNR (cli) = %d, status = 0x' % data.CliForSNRL2P,
                    '%.02X',
                    data.L2CX, self.decoder.SCHANNEL_STATUS_DECODE, group=4)
    self.Send(indent + 2, (('C1-L1 = %.2fm, P2-C1 = %.2fm, P2-L1 = %.2fm, '
                            + 'L2-L1 = %.2fm, P2-P1 = %.2fm, NCO ofs = %dHz')
                           % (data.C1_L1, data.P2_C1, data.P2_L1,
                              data.L2_L1, data.P2_P1, data.NCOHz)))

  def _DumpSSVAlmanData(self, indent, data):
    self.Send(indent,
              'PRN %d: change count = %d, predicted Doppler = %dHz'
              % (data.SV, data.CountUpdate, data.DoppHz))
    out_list = [self._FormatElAz(data.Elev, data.Azimuth)]
    out_list.append(self._FormatVH('almanac', data.AlmVFlag, data.AlmHealth))
    self.Send(indent + 2, ', '.join(out_list))

  def FormatBin1(self, item):
    """Format a Bin1 message."""
    parsed = item.parsed
    decoded = item.decoded
    dtime_str = self.GetDateTimeStr(decoded.dtime)
    navmode = self.DecodeEnum(parsed.NavMode, self.decoder.BIN1_NAVMODE_DECODE)
    decode_list = ['%s: NavMode = %s with %d satellites'
                   % (dtime_str, navmode, parsed.NumOfSats)]
    self.Send(2, ', '.join(decode_list))
    decode_list = ['Stddev of residuals = %.3fm' % parsed.StdDevResid]
    if decoded.diff_age is not None:
      decode_list.append('Diff age = %d secs' % decoded.diff_age)
    self.Send(3, ', '.join(decode_list))
    alt_str = self.EncodeAlt(parsed.Height)
    decode_str = ['%.7f,%.7f' % (parsed.Latitude, parsed.Longitude)]
    decode_str.append('Altitude %s (ellipsoidal)' % alt_str)
    self.Send(4, ', '.join(decode_str))
    decode_list = ['Speed %.3f m/s @ %.2f True'
                   % (decoded.speed, decoded.track)]
    decode_list.append('(%.3f m/s E, %.3f m/s N, %.3f m/s U)'
                       % (parsed.VEast, parsed.VNorth, parsed.Vup))
    self.Send(4, ', '.join(decode_list))
  FORMATTER_DICT[PARSER.GetParser(1)] = FormatBin1

  def FormatBin2(self, item):
    """Format a Bin2 message."""
    parsed = item.parsed
    decoded = item.decoded
    tracked = ','.join(['%02d' % s for s in decoded.tracked])
    used = ','.join(['%02d' % s for s in decoded.used])
    self.Send(2, ('GPS satellites tracked = %s; used = %s'
                  % (tracked or '(none)', used or '(none)')))
    self.Send(3, ('HDOP = %.1f, VDOP = %.1f, GPS-UTC offset = %d secs'
                  % (decoded.hdop, decoded.vdop, parsed.GpsUtcDiff)))
    waas_list = ['SBAS tracking = 0x%.04X' % parsed.WAASMask]
    if decoded.waas_tracked or decoded.waas_used or True:  ### Temp force
      waas_tracked = ','.join(['%02d' % s for s in decoded.waas_tracked])
      waas_used = ','.join(['%02d' % s for s in decoded.waas_used])
      waas_list.append('tracked = %s; used = %s'
                       % (waas_tracked or '(none)', waas_used or '(none)'))
    self.Send(3, ': '.join(waas_list))
  FORMATTER_DICT[PARSER.GetParser(2)] = FormatBin2

  def FormatBin62(self, item):
    """Format a Bin62 message."""
    parsed = item.parsed
    decoded = item.decoded
    self.Send(2, ('Slot %d, K number %+d, Ktag_ch = 0x%02X, Spare1 = 0x%.04x'
                  % (parsed.SV, decoded.knum, parsed.Ktag_ch, parsed.Spare1)))
    self.DumpBitStrings(4, self.decoder.BIN62_STRINGS, decoded.strings)
  FORMATTER_DICT[PARSER.GetParser(62)] = FormatBin62

  def FormatBin65(self, item):
    """Format a Bin65 message."""
    parsed = item.parsed
    decoded = item.decoded
    self.Send(2, (('Slot %d, K number = %+d, Spare1 = 0x%.04x, '
                   + 'time received = %d')
                  % (parsed.SV, decoded.knum, parsed.Spare1,
                     parsed.TimeReceivedInSeconds)))
    self.DumpBitStrings(4, self.decoder.BIN65_STRINGS, decoded.strings)
  FORMATTER_DICT[PARSER.GetParser(65)] = FormatBin65

  def FormatBin66(self, item):
    """Format a Bin66 message."""
    parsed = item.parsed
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    self.Send(2, ('At %s (Spare1 = 0x%.02X, Spare2 = %.04X):'
                  % (dtime_str, parsed.Spare1, parsed.Spare2)))
    self._DumpObservations(4, decoded.sat_obs, label='Slot', show_knum=True)
  FORMATTER_DICT[PARSER.GetParser(66)] = FormatBin66

  def FormatBin69(self, item):
    """Format a Bin69 message."""
    parsed = item.parsed
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    l1_str = ','.join(['%02d' % s for s in decoded.l1_used]) or '(none)'
    l2_str = ','.join(['%02d' % s for s in decoded.l2_used]) or '(none)'
    self.Send(2, ('%s: G1/G2 chans used = %s / %s'
                  % (dtime_str, l1_str, l2_str)))
    self.Send(3, ('Spare01 = 0x%.02X, Spare02 = 0x%.02X'
                  % (parsed.Spare01, parsed.Spare02)))
    for data in decoded.data:
      self._DumpSGLONASSChanData(4, data)
  FORMATTER_DICT[PARSER.GetParser(69)] = FormatBin69

  def FormatBin76(self, item):
    """Format a Bin76 message."""
    parsed = item.parsed
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    self.Send(2, ('At %s (Spare1 = 0x%.02X, Spare2 = %.04X):'
                  % (dtime_str, parsed.Spare1, parsed.Spare2)))
    self._DumpObservations(4, decoded.sat_obs)
  FORMATTER_DICT[PARSER.GetParser(76)] = FormatBin76

  def FormatBin80(self, item):
    """Format a Bin80 message."""
    parsed = item.parsed
    decoded = item.decoded
    self.Send(2, ('From PRN %d at GPS second %d of this week (Spare = 0x%.04X):'
                  % (parsed.PRN, parsed.MsgSecOfWeek, parsed.Spare)))
    self.DumpULongs(4, 'WAAS data', parsed.WaasMsg)
    if self.fmt_level < self.FMT_WAAS_BASIC:
      return
    self.Send(6, ('Preamble = 0x%02X, Type = %d, CRC = 0x%06X (pad = 0x%02X)'
                  % (decoded.preamble, decoded.type, decoded.crc, decoded.pad)))
  FORMATTER_DICT[PARSER.GetParser(80)] = FormatBin80

  def FormatBin89(self, item):
    """Format a Bin89 message."""
    decoded = item.decoded
    tracked_str = ','.join([str(s) for s in decoded.tracked]) or '(none)'
    used_str = ','.join([str(s) for s in decoded.used]) or '(none)'
    self.Send(2, ('At second %d of this GPS week, SBAS tracked = %s, used = %s'
                  % (item.parsed.GPSSecOfWeek, tracked_str, used_str)))
    for data in decoded.data:
      self._DumpSChannelData(4, data)
  FORMATTER_DICT[PARSER.GetParser(89)] = FormatBin89

  def FormatBin93(self, item):
    """Format a Bin93 message."""
    parsed = item.parsed
    decoded = item.decoded
    self.Send(2, (('For PRN %d (flags = 0x%.02X) at GPS second %d '
                   + 'of this week, (Spare = 0x%.04X):')
                  % (parsed.SV, parsed.Flags, parsed.TOWSecOfWeek, parsed.Spare)))
    self.Send(4, ('TO = %ds, IODE = %d, URA = %d'
                  % (parsed.TO, parsed.IODE, parsed.URA)))
    self.Send(6, ('XG / YG / ZG = %.2fm / %.2fm / %.2fm'
                  % (decoded.XG, decoded.YG, decoded.ZG)))
    self.Send(6, ('XG. / YG. / ZG. = %.6em/s / %.6em/s / %.6em/s'
                  % (decoded.XGDot, decoded.YGDot, decoded.ZGDot)))
    self.Send(6, (('XG.. / YG.. / ZG.. = %.6em/s^2 / %.6em/s^2 '
                   + '/ %.6em/s^2')
                  % (decoded.XGDotDot, decoded.YGDotDot, decoded.ZGDotDot)))
    self.Send(6, ('Gf0 = %.6es, Gf0. = %.6es/s'
                  % (decoded.Gf0, decoded.Gf0Dot)))
  FORMATTER_DICT[PARSER.GetParser(93)] = FormatBin93

  def FormatBin94(self, item):
    """Format a Bin94 message."""
    parsed = item.parsed
    decoded = item.decoded
    alpha_list = self.FormatTuple('%s = %.6e', decoded.alphas)
    beta_list = self.FormatTuple('%s = %.6e', decoded.betas)
    utc_list = self.FormatTuple('%s = %.6e', decoded.utcs)
    time_list = ['UTC conversion params:', ', '.join(utc_list)]
    time_list.append('at week/sec %d/%d' % (parsed.wnt, parsed.tot))
    time_list.append('(%s)' % self.GetDateTimeStr(decoded.dtime, 0))
    leap_list = ['Leap seconds: current = %d, future = %d'
                 % (parsed.dtis, parsed.dtisf)]
    leap_list.append('effective after week/day %d/%d'
                     % (parsed.wnisf, parsed.dn))
    leap_list.append('(at %s)' % self.GetDateTimeStr(decoded.nleap_dtime, 0))
    self.Send(2, 'AFCRL Ionosphere alpha params: ' + ', '.join(alpha_list))
    self.Send(2, 'AFCRL Ionosphere beta params: ' + ', '.join(beta_list))
    self.Send(2, ' '.join(time_list))
    self.Send(2, ' '.join(leap_list))
  FORMATTER_DICT[PARSER.GetParser(94)] = FormatBin94

  def FormatBin95(self, item):
    """Format a Bin95 message."""
    parsed = item.parsed
    self.Send(2, (('Ephemeris data for satellite %d at GPS second of week %d, '
                   + 'Spare1 = 0x%.04X:')
                  % (parsed.SV, item.decoded.RealSecOfWeek, parsed.Spare1)))
    sf_list = [[parsed.SF1words, 'SF1'], [parsed.SF2words, 'SF2'],
               [parsed.SF3words, 'SF3']]
    for value, name in sf_list:
      self.DumpULongs(2, name, value)
  FORMATTER_DICT[PARSER.GetParser(95)] = FormatBin95

  def FormatBin96(self, item):
    """Format a Bin96 message."""
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    self.Send(2, 'At %s (Spare1 = 0x%.04X):' % (dtime_str, item.parsed.Spare1))
    self._DumpObservations(4, decoded.sat_obs)
  FORMATTER_DICT[PARSER.GetParser(96)] = FormatBin96

  def FormatBin97(self, item):
    """Format a Bin97 message."""
    parsed = item.parsed
    decoded = item.decoded
    self.Send(2, ('CPU utilization %.1f%% available, max subframes queued = %d'
                  % (decoded.cpu_unused, parsed.MaxSubFramePnd)))
    missed_list = []
    for name, value in [['subframes', parsed.MissedSubFrame],
                        ['code accumulation measurements', parsed.MissedAccum],
                        ['pseudorange measurements', parsed.MissedMeas]]:
      if value:
        missed_list.append('%s = %d' % (name, value))
    if missed_list:
      self.Send(3, 'Missed: ' + ', '.join(missed_list))
    if sum(decoded.spares):
      self.DumpULongs(3, 'Spares[1-5]', decoded.spares)
  FORMATTER_DICT[PARSER.GetParser(97)] = FormatBin97

  def FormatBin98(self, item):
    """Format a Bin98 message."""
    parsed = item.parsed
    out_list = ['Last almanac processed = %d' % parsed.LastAlman]
    iono = self.DecodeEnum(parsed.IonoUTCVFlag,
                           self.decoder.SCHANNEL_VALIDITY_DECODE)
    out_list.append('extracted ionosphere model validity = %s' % iono)
    self.Send(2, ', '.join(out_list))
    for ssva in item.decoded:
      self._DumpSSVAlmanData(4, ssva)
  FORMATTER_DICT[PARSER.GetParser(98)] = FormatBin98

  def FormatBin99(self, item):
    """Format a Bin99 message."""
    parsed = item.parsed
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    navmode_str = self.DecodeEnum(decoded.navmode,
                                  self.decoder.BIN99_NAVMODE_DECODE)
    navmode_diff_str = ' with diff' if decoded.diff else ''
    self.Send(2, ('%s: NavMode = %s%s'
                  % (dtime_str, navmode_str, navmode_diff_str)))
    if self.fmt_level < self.FMT_UPDATED:
      decode_list = ['Clock frequency error = %dHz at L1 freq'
                     % parsed.ClockErrAtL1]
    else:
      decode_list = ['Clock frequency error = %d Hz at L1 freq'
                     % parsed.ClockErrAtL1]
    decode_list.append('GPS-UTC offset = %d secs' % parsed.UTCTimeDiff)
    self.Send(3, ', '.join(decode_list))
    for data in decoded.data:
      self._DumpSChannelData(4, data)
  FORMATTER_DICT[PARSER.GetParser(99)] = FormatBin99

  def FormatBin100(self, item):
    """Format a Bin100 message."""
    decoded = item.decoded
    dtime_str = self.GetWeekTowStr(decoded.dtime)
    navmode_str = self.DecodeEnum(decoded.navmode,
                                  self.decoder.BIN99_NAVMODE_DECODE)
    navmode_diff_str = ' with diff' if decoded.diff else ''
    self.Send(2, ('%s: NavMode = %s%s'
                  % (dtime_str, navmode_str, navmode_diff_str)))
    l1p_str = ','.join([str(s) for s in decoded.l1p_used]) or '(none)'
    l2p_str = ','.join([str(s) for s in decoded.l2p_used]) or '(none)'
    self.Send(4, 'Satellites used: L1P = %s, L2P = %s' % (l1p_str, l2p_str))
    for data in decoded.data:
      self._DumpSChannelL2Data(6, data)
  FORMATTER_DICT[PARSER.GetParser(100)] = FormatBin100


class Formatter(NmeaFormatter, BinaryFormatter):
  """Class for combined formatter."""
  EXTRACTER = hemisphere.Extracter
  PARSER = hemisphere.Parser
  DECODER = hemisphere.Decoder

  FORMATTER_DICT = NmeaFormatter.FORMATTER_DICT.copy()
  FORMATTER_DICT.update(BinaryFormatter.FORMATTER_DICT)
