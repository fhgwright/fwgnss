"""Module for formatting of NMEA-0183 data into human-friendly form."""

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
from ..parse import nmea


class Constants(nmea.Constants):  # pylint: disable=too-few-public-methods
  """Class for various constant definitions."""


class NmeaFormatter(generic.Formatter):
  """Class for NMEA formatter objects."""
  EXTRACTER = nmea.NmeaExtracter
  PARSER = nmea.NmeaParser
  DECODER = nmea.NmeaDecoder

  FORMATTER_DICT = {}

  # Pylint seems to be too dumb to realize that the 'decoder' instance
  # variable here will point to an instance of nmea.Decoder, rather
  # than parse_gnss.Decoder, and it complains about various missing members.
  # The only non-obnoxious solution seems to be to disable that error.
  #
  # It should probably be temporarily undisabled after any major changes.
  #
  # pylint: disable=no-member

  @staticmethod
  def FormatSat(view):
    """Format a single satellite view."""
    sat_type = Constants.SAT_TYPE_LETTERS[view.type]
    return '%s-%02d(%02d)' % (sat_type, view.num, view.sat)

  def FormatGGA(self, item):
    """Format an xxGGA item."""
    parsed = item.parsed
    fix_str = self.DecodeChar(parsed.qual, self.decoder.GGA_QUALITY_DECODE)
    self._CommonGGA(parsed, item.decoded, fix_str)
  FORMATTER_DICT[PARSER.GetParser('GPGGA')] = FormatGGA

  def FormatGNS(self, item):
    """Format an xxGNS item."""
    parsed = item.parsed
    self._CommonGGA(parsed, item.decoded, '')
    if parsed.mode:
      mode_strings = self._DecodeNavModes(parsed.mode)
      self.Send(4, 'Mode: %s' % ', '.join(mode_strings))
  FORMATTER_DICT[PARSER.GetParser('GPGNS')] = FormatGNS

  def _CommonGGA(self, parsed, decoded, fix_str):
    decode_list = ['%s UTC:' % self.EncodeTime(decoded.time)]
    sats = decoded.num_sats
    if fix_str:
      decode_list += [' Fix = %s' % fix_str]
      if sats:
        decode_list += [' from']
    if sats:
      decode_list += [' %d Satellites' % sats]
    if decoded.hdop:
      decode_list += [', HDOP = %.1f' % decoded.hdop]
    if decoded.age:
      decode_list += [', Diff age = %.1f secs from %s'
                      % (decoded.age, parsed.refid)]
    self.Send(2, ''.join(decode_list))
    if decoded.lat is None or decoded.lon is None:
      return
    pos_list = ['%.7f%s,%.7f%s'
                % (decoded.lat, decoded.lat_h, decoded.lon, decoded.lon_h)]
    if decoded.alt is not None:
      pos_list += [', Altitude %s' % self.EncodeAlt(decoded.alt, decoded.alt_u)]
      if decoded.geoid is not None and decoded.alt_u == decoded.geoid_u:
        pos_list += [' (%s ellipsoidal)'
                     % self.EncodeAlt(decoded.alt + decoded.geoid,
                                      decoded.alt_u)]
    self.Send(3, ''.join(pos_list))

  def _DecodeNavModes(self, navmode):
    mode_strings = []
    for system, mode in zip(Constants.SYSTEM_NAMES, navmode):
      mode_string = self.DecodeChar(mode, self.decoder.NAV_MODE_DECODE)
      mode_strings.append('%s = %s' % (system, mode_string))
    return mode_strings

  def FormatGLL(self, item):
    """Format an xxGLL item."""
    decoded = item.decoded
    time_str = self.EncodeTime(decoded.time)
    latlon_str = ('%.7f%s,%.7f%s'
                  % (decoded.lat, decoded.lat_h, decoded.lon, decoded.lon_h))
    status_str = self.DecodeChar(item.parsed.status,
                                 self.decoder.RMC_STATUS_DECODE)
    self.Send(2, ('%s UTC: %s, Status = %s'
                  % (time_str, latlon_str, status_str)))
  FORMATTER_DICT[PARSER.GetParser('GPGLL')] = FormatGLL

  def FormatVTG(self, item):
    """Format an xxVTG item."""
    parsed = item.parsed
    decoded = item.decoded
    if not (decoded.track_t or decoded.speed_n):
      if self.fmt_level < self.FMT_UPDATED:
        self.Send(2, 'Speed 0.00  (0.00 ) @ 0.00 ')
      return
    track_tu = self.decoder.UNITS_MAP.get(parsed.track_t[1]) or '?'
    track_mu = self.decoder.UNITS_MAP.get(parsed.track_m[1]) or '?'
    speed_nu = self.decoder.UNITS_MAP.get(parsed.speed_n[1]) or '?'
    speed_ku = self.decoder.UNITS_MAP.get(parsed.speed_k[1]) or '?'
    track_str = '%.2f %s' % (decoded.track_t, track_tu)
    if decoded.track_m is not None:
      track_str += ' (%.2f %s)' % (decoded.track_m, track_mu)
    if speed_ku == 'Kph':
      speed_str = ('%.2f %s (%.2f %s, %.3f m/s)'
                   % (decoded.speed_n, speed_nu, decoded.speed_k, speed_ku,
                      decoded.speed_k * (1000.0 / 3600.0)))
    else:
      speed_str = '%.2f %s (%.2f %s)' % (decoded.speed_n, speed_nu,
                                         decoded.speed_k, speed_ku)
    self.Send(2, 'Speed %s @ %s' % (speed_str, track_str))
  FORMATTER_DICT[PARSER.GetParser('GPVTG')] = FormatVTG

  def FormatZDA(self, item):
    """Format an xxZDA item."""
    decoded = item.decoded
    dtime = decoded.dtime
    dt_list = ['%s UTC' % self.EncodeDateTime(dtime)]
    gps_datetime = self.EncodeGPSDateTime(dtime)
    if gps_datetime:
      dt_list.append(', GPS week/second = ' + gps_datetime)
    zone = decoded.zone
    if zone:
      dt_list.append(' (local zone = %.02d:%.02d)' % divmod(zone, 60))
    self.Send(2, ''.join(dt_list))
  FORMATTER_DICT[PARSER.GetParser('GPZDA')] = FormatZDA

  def FormatRMC(self, item):
    """Format an xxRMC item."""
    parsed = item.parsed
    decoded = item.decoded
    datetime_str = self.EncodeDateTime(decoded.dtime)
    status_str = self.DecodeChar(parsed.status, self.decoder.RMC_STATUS_DECODE)
    self.Send(2, '%s UTC: Status = %s' % (datetime_str, status_str))
    if decoded.lat is not None and decoded.lon is not None:
      loc_list = ['%.7f%s,%.7f%s'
                  % (decoded.lat, decoded.lat_h, decoded.lon, decoded.lon_h)]
      if decoded.speed_n is not None and decoded.track_t is not None:
        loc_list.append(', %.2f Kt (%.3f m/s) @ %.2f True'
                        % (decoded.speed_n, decoded.speed_n * (1852.0 / 3600.0),
                           decoded.track_t))
        if decoded.mag_var is not None:
          if self.fmt_level < self.FMT_UPDATED:
            hemi = 'W' if decoded.mag_var < 0 else 'E'
            loc_list.append(' (var %.2f%s)' % (abs(decoded.mag_var), hemi))
          else:
            loc_list.append(' (var %+.2f)' % decoded.mag_var)
        self.Send(3, ''.join(loc_list))
    if parsed.mode:
      self.Send(4, 'Mode: %s' % ', '.join(self._DecodeNavModes(parsed.mode)))
    if parsed.navstat:
      navstat_str = self.DecodeChar(parsed.navstat,
                                    self.decoder.RMC_NAVSTAT_DECODE)
      self.Send(3, 'Nav status = %s' % navstat_str)
  FORMATTER_DICT[PARSER.GetParser('GPRMC')] = FormatRMC

  def FormatDTM(self, item):
    """Format an xxDTM item."""
    parsed = item.parsed
    decoded = item.decoded
    decode_list = ['Local datum = %s' % parsed.datum]
    if parsed.subdiv:
      decode_list += [' (%s)' % parsed.subdiv]
    if ((decoded.latoff or decoded.lonoff or decoded.altoff)
        and not (decoded.latoff_h or decoded.lonoff_h)):
      decode_list += [', ENU offset %.5f\', %.5f\' | %.3fm'
                      % (decoded.lonoff * 60.0, decoded.latoff * 60.0,
                         decoded.altoff)]
    decode_list += [', Reference datum = %s' % parsed.ref_dtm]
    self.Send(2, ''.join(decode_list))
  FORMATTER_DICT[PARSER.GetParser('GPDTM')] = FormatDTM

  def FormatGSA(self, item):
    """Format an xxGSA item."""
    parsed = item.parsed
    decoded = item.decoded
    mode_str = self.DecodeChar(parsed.acq_mode,
                               self.decoder.GSA_ACQ_MODE_DECODE)
    pos_mode_str = self.DecodeChar(parsed.pos_mode,
                                   self.decoder.GSA_POS_MODE_DECODE)
    if parsed.system:
      system_str = ' for system ' + self.DecodeNum(decoded.system,
                                                   Constants.SYSTEM_DECODE)
    else:
      system_str = ''
    num_sats = len(decoded.sat_list)
    if not (decoded.pdop or decoded.hdop or decoded.vdop):
      return  ### Suppress rest in this case for now
    self.Send(2, ('Acquisition mode %s, position mode %s%s'
                  % (mode_str, pos_mode_str, system_str)))
    try:
      dop_str = ('PDOP = %.1f, HDOP = %.1f, VDOP = %.1f'
                 % (decoded.pdop, decoded.hdop, decoded.vdop))
    except TypeError:
      pass
    else:
      self.Send(3, '%s from %d satellites' % (dop_str, num_sats))
    for signal, residuals in decoded.sig_residuals:
      self._DumpResiduals(4, residuals, signal)
  FORMATTER_DICT[PARSER.GetParser('GPGSA')] = FormatGSA

  def FormatGRS(self, item):
    """Format an xxGRS item."""
    parsed = item.parsed
    decoded = item.decoded
    time_str = self.EncodeTime(decoded.time)
    mode_str = self.DecodeNum(decoded.mode, self.decoder.GRS_MODE_DECODE)
    decode_str = '%s UTC: Mode = %s' % (time_str, mode_str)
    if parsed.system:
      decode_str += ', System = %s' % self.DecodeNum(decoded.system,
                                                     Constants.SYSTEM_DECODE)
    if parsed.signal:
      decode_str += ', Signal = %s' % self.DecodeNum(decoded.signal,
                                                     Constants.SIGNAL_DECODE)
    self.Send(2, decode_str)
    if decoded.sat_residuals:
      self._DumpResiduals(4, decoded.sat_residuals)
  FORMATTER_DICT[PARSER.GetParser('GPGRS')] = FormatGRS

  def _DumpResiduals(self, indent, residuals, signal=None):
    if signal is not None:
      signal_str = ' for signal ' + self.DecodeNum(signal,
                                                   Constants.SIGNAL_DECODE)
    else:
      signal_str = ''
    self.Send(indent, 'Range residuals%s:' % signal_str)
    for res in residuals:
      sat = self.FormatSat(res)
      self.Send(indent + 2, '%s: %.3fm' % (sat, res.value))

  def FormatGSV(self, item, error=False):
    """Format an xxGSV item."""
    decoded = item.decoded
    if not decoded.sat_views:
      return
    track_str = 'Was tracking' if error else 'Tracking'
    indent = 4 if error else 2
    self._DumpGSV(indent, track_str, item.parsed, decoded, decoded.sat_views)
  FORMATTER_DICT[PARSER.GetParser('GPGSV')] = FormatGSV
  FORMATTER_DICT[PARSER.GetParser('GLGSV')] = FormatGSV
  FORMATTER_DICT[PARSER.GetParser('GAGSV')] = FormatGSV
  FORMATTER_DICT[PARSER.GetParser('GBGSV')] = FormatGSV

  def _DumpGSV(self,  # pylint: disable=too-many-arguments
               indent, prefix, parsed, decoded, sat_data):
    if parsed.signal:
      signal_str = ' ' + self.DecodeNum(decoded.signal, Constants.SIGNAL_DECODE)
    else:
      signal_str = ''
    try:
      system_str = ' ' + Constants.SYSTEM_DECODE[decoded.system]
    except KeyError:
      system_str = ''
    in_view = decoded.in_view
    visible = len(sat_data)
    if visible != in_view:
      visibility_str = '%d(%d)' % (visible, in_view)
    else:
      visibility_str = '%d' % in_view
    self.Send(indent, ('%s signal%s from %d out of %s visible%s satellites'
                       % (prefix, signal_str, decoded.tracked,
                          visibility_str, system_str)))
    for view in sat_data:
      sat = self.FormatSat(view)
      try:
        self.Send(indent+2, ('%s: %02d @ %03d, %s dBHz'
                             % (sat, view.elev, view.az, view.snr or '--')))
      except TypeError:
        self.Send(indent+2, ('%s: %2s @ %3s, %s dBHz'
                             % (sat,
                                view.elev or '--', view.az or '---',
                                view.snr or '--')))

  def FormatGST(self, item):
    """Format an xxGST item."""
    decoded = item.decoded
    time_str = self.EncodeTime(decoded.time) + ' UTC'
    if decoded.rms_err is None:
      self.Send(2, '%s: --' % time_str)
      return
    self.Send(2, ('%s: range residuals (RMS) = %.3fm'
                  % (time_str, decoded.rms_err)))
    self.Send(3, ('Horizontal error ellipse = %.3fm x %.3fm @ %.2f True'
                  % (decoded.major_err, decoded.minor_err, decoded.major_dir)))
    self.Send(3, ('Latitude, longitude | altitude error = %.3fm, %.3fm | %.3fm'
                  % (decoded.lat_err, decoded.lon_err, decoded.alt_err)))
  FORMATTER_DICT[PARSER.GetParser('GPGST')] = FormatGST

  def FormatRRE(self, item):
    """Format an xxRRE item."""
    decoded = item.decoded
    self.Send(2, (('Horizontal error = %.3fm, vertical error = %.3fm'
                   + ' from %d satellites')
                  % (decoded.horiz_err, decoded.vert_err, decoded.num_used)))
    if decoded.residuals:
      self._DumpResiduals(4, decoded.residuals)
  FORMATTER_DICT[PARSER.GetParser('GPRRE')] = FormatRRE

  def FormatGBS(self, item, extra=None):  # pylint: disable=invalid-name
    """Format a GBS sentence."""
    # The extra arg allows an insertion for the PSAT,GBS case
    decoded = item.decoded
    self.Send(2, 'For data at %s UTC:' % self.EncodeTime(decoded.time))
    if (decoded.lat_err or decoded.lon_err or decoded.alt_err
        or self.fmt_level < self.FMT_UPDATED):
      try:
        self.Send(4, (('Expected latitude / longitude | altitude error = '
                       + '%.3fm / %.3fm | %.3fm')
                      % (decoded.lat_err, decoded.lon_err, decoded.alt_err)))
      except TypeError:
        pass
    if decoded.bad_sat:
      self.Send(4, (('%.1f%% probability that %s failed'
                     + ' with range bias of %.3fm +/- %.3fm')
                    % (decoded.fault_prob, self.FormatSat(decoded.bad_sat),
                       decoded.range_bias, decoded.range_bias_sd)))
    elif self.fmt_level < self.FMT_UPDATED:
      return
    status_list = extra or []
    if decoded.system:
      status_list.append(' for system %s'
                         % self.DecodeChar(decoded.system,
                                           Constants.SYSTEM_DECODE))
    if decoded.signal:
      status_list.append(', signal %s'
                         % self.DecodeChar(decoded.signal,
                                           Constants.SIGNAL_DECODE))
    self.Send(4, ''.join(status_list))
  FORMATTER_DICT[PARSER.GetParser('GPGBS')] = FormatGBS


class Formatter(NmeaFormatter):
  """Class for generic NMEA formatter."""
