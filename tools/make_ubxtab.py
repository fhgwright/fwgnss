#!/usr/bin/env python

from __future__ import print_function

import re
import sys

PAT1_RE = re.compile(r'UBX-(?P<grpnam>\w+),(?P<grpnum>[0-9A-Fx]+)\Z')
PAT2_RE = re.compile(r'UBX-(?P<grpnam>\w+)-(?P<msgnam>\w+)'
                     r',(?P<grpnum>[0-9A-Fx]+),(?P<msgnum>[0-9A-Fx]+)\Z')


def parse_line(line):
  sline = line.strip()
  match = PAT2_RE.match(sline)
  if match:
    matches = match.groupdict();
    try:
      matches['grpnum'] = int(matches['grpnum'], 16)
      matches['msgnum'] = int(matches['msgnum'], 16)
    except ValueError:
      return None
    else:
      return matches
  match = PAT1_RE.match(sline)
  if match:
    matches = match.groupdict();
    try:
      matches['grpnum'] = int(matches['grpnum'], 16)
    except ValueError:
      return None
    else:
      return matches
  return None


def parse_lines(lines):
  result = {}
  for line in lines:
    parsed = parse_line(line)
    if not parsed:
      continue
    grpnam = parsed['grpnam']
    grpnum = parsed['grpnum']
    msgnam = parsed.get('msgnam')
    msgnum = parsed.get('msgnum')
    if msgnam and msgnum:
      result[(grpnum, msgnum)] = '%s-%s' % (grpnam, msgnam)
    else:
      result[grpnum] = grpnam
  return result


def format_lines(table, prefix=''):
  result = [prefix + '{']
  keys = sorted(table.keys())
  for key in keys:
    result.append('    %s: %s,' % (repr(key), repr(table[key])))
  result.append('}')
  return result


def main(argv):
  prefix = argv[1] if len(argv) > 1 else ''
  output = format_lines(parse_lines(sys.stdin), prefix)
  for line in output:
    print(line)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
