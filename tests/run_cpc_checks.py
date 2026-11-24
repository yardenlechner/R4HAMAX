"""Exercise the experimental CPC path in the production REXX source.

Usage: python tests/run_cpc_checks.py /path/to/regina
Python standard library only. Fixtures are synthetic desktop ASCII,
not production SMF or an EBCDIC/TSO acceptance test.
Fixture identities and example measurements are invented for these
tests; no site records or user measurement examples are imported.
"""
from dataclasses import dataclass, replace
import csv
import datetime as dt
from fractions import Fraction
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work'
WORK.mkdir(exist_ok=True)
REXX = sys.argv[1] if len(sys.argv) > 1 else shutil.which('regina')
if not REXX:
    raise SystemExit('Install Regina REXX or pass its executable path')
SOURCE = (ROOT / 'src/R4HAMAX.rexx').read_text(encoding='ascii')
DAY = dt.datetime(2026, 9, 8)
DAY_ARG = DAY.strftime('%Y%j')
CPC_A = b'PLTA0000000000000001'
CPC_B = b'PLTB0000000000000001'
DEFAULT = f'CPC=Y DATE={DAY_ARG} SID=* HOURLY=Y'
PASSED = []


@dataclass(frozen=True)
class Sample:
    cpc: bytes
    ptn: int
    start: dt.datetime
    lac: int
    sid: str = 'SYSA'
    duration_ms: int = 900000
    scope: bool = True
    lgo: int = 0
    sysplex: str = 'PLEX1'
    sysname: str = ''
    flags: int = 0
    wla: int = 0
    hof: int = 0
    inb: int = 0


def binary(sample):
    """Independent IBM-layout record; offsets include the absent RDW.

    Nine triplets, Product 100/104, CPU control 204/344 differ from the
    production REXX fixture, and physical LPAR numbers are explicit.
    """
    record = bytearray(544)

    def put(offset, value):
        record[offset - 4:offset - 4 + len(value)] = value

    def text(value, size):
        return value.encode('ascii').ljust(size, b' ')

    year = sample.start.year - 1900
    julian = int(sample.start.strftime('%j'))
    mins, remain = divmod(sample.duration_ms, 60000)
    secs, millis = divmod(remain, 1000)
    date = bytes.fromhex(f'0{year:03d}{julian:03d}F')
    time = bytes.fromhex(sample.start.strftime('0%H%M%SF'))
    duration = bytes.fromhex(f'{mins:02d}{secs:02d}{millis:03d}F')
    put(4, b'\xc0\x46')
    put(14, text(sample.sid, 4))
    put(18, b'RMF ')
    put(22, struct.pack('>HH', 1, 9))
    put(28, struct.pack('>IHHIHH', 100, 104, 1, 204, 344, 1))
    put(102, b'RMF     ')
    put(110, time + date + duration)
    put(130, sample.flags.to_bytes(2, 'big'))
    put(150, sample.ptn.to_bytes(1, 'big'))
    put(160, sample.lgo.to_bytes(8, 'big', signed=False))
    put(188, text(sample.sysplex, 8))
    put(196, text(sample.sysname or f'LPAR{sample.ptn:04d}', 8))
    put(208, bytes([sample.inb, 0x10 if sample.scope else 0]))
    put(236, struct.pack('>I', sample.wla))
    put(240, struct.pack('>I', sample.lac))
    put(244, sample.hof.to_bytes(8, 'big'))
    put(278, sample.cpc)
    return bytes(record)


def sample_hour(cpc, ptn, hour, values, **kwargs):
    return [Sample(cpc, ptn, DAY + dt.timedelta(hours=hour, minutes=15*i),
                   value, **kwargs)
            for i, value in enumerate(values)]


def map_text(cpc, ptn):
    return f'{cpc.hex().upper()} {ptn}'


def source_driver(name, scenario, io=''):
    source = SOURCE.replace('call initialize\n',
                            'call initialize\ncall scenario\nexit 0\n', 1)
    if io:
        source = source.replace('address TSO ', 'call fakeIo ')
    path = WORK / f'cpc_{name}.rexx'
    path.write_text(source + '\nscenario:\n' + scenario + '\nreturn\n' + io,
                    encoding='ascii')
    return path


def execute(path, args='', expected=0, contains=None):
    result = subprocess.run([REXX, str(path), args], capture_output=True,
                            text=True, timeout=30)
    # Windows Regina may normalize nonzero process exit values to 1.
    if sys.platform == 'win32':
        valid_rc = (result.returncode == 0) == (expected == 0)
    else:
        valid_rc = result.returncode == expected
    assert valid_rc, (path.name, args, expected, result.returncode,
                      result.stdout, result.stderr)
    if contains is not None:
        assert contains in result.stdout, (path.name, contains, result.stdout)
    return result.stdout


METRICS = """
do ci = 1 to g.cpcCount
  ck = g.cpcKey.ci
  say 'CHECK_CPC' ck g.cpcComplete.ck g.cpcIncomplete.ck
  if g.cpcComplete.ck > 0 then
    say 'CHECK_PEAK' ck g.cpcPeak.ck g.cpcPeakHour.ck
  do li = 1 to g.cpcPartCount.ck
    pk = g.cpcPart.ck.li
    do hr = 0 to 23
      say 'CHECK_LPAR' ck g.cpcPtn.pk hr ,
        g.cpcN.pk.hr g.cpcSum.pk.hr
    end
  end
end
say 'CHECK_COUNTS' g.validCnt g.dupCnt
"""


def scenario(records=(), inventory=(), *, params=DEFAULT, after='',
             raw_map=(), do_report=True):
    lines = ['g.testing = 1', f"call parameters '{params}'"]
    lines.extend(f"call cpcMapLine '{map_text(cpc, ptn)}'"
                 for cpc, ptn in inventory)
    lines.extend(f"call cpcMapLine '{line}'" for line in raw_map)
    lines.extend(f"call process x2c('{binary(item).hex()}')"
                 for item in records)
    if do_report:
        lines += ['call report', 'do oi = 1 to g.outputCnt',
                  '  say g.output.oi', 'end', METRICS]
    if after:
        lines.append(after)
    return '\n'.join(lines)


def run_case(name, records=(), inventory=(), **kwargs):
    expected = kwargs.pop('expected', 0)
    contains = kwargs.pop('contains', None)
    output = execute(source_driver(name, scenario(records, inventory, **kwargs)),
                     expected=expected, contains=contains)
    PASSED.append(name)
    return output


def oracle(records, inventory):
    """Fraction oracle, independent from REXX and its internal stems."""
    unique = {}
    for sample in records:
        middle = sample.start + dt.timedelta(microseconds=sample.duration_ms*500)
        if middle.date() != DAY.date():
            continue
        key = (sample.cpc, sample.ptn, sample.start, sample.duration_ms)
        signature = (sample.lac, sample.scope)
        if key in unique:
            assert unique[key][0] == signature, 'conflicting oracle fixture'
            continue
        unique[key] = (signature, sample)
    per_hour = {}
    for cpc, ptn in inventory:
        for hour in range(24):
            per_hour[cpc, ptn, hour] = []
    for _, sample in unique.values():
        per_hour[sample.cpc, sample.ptn, sample.start.hour].append(sample)
    cpc_hours = {}
    for cpc in {x[0] for x in inventory}:
        members = [ptn for candidate, ptn in inventory if candidate == cpc]
        for hour in range(24):
            values = []
            for ptn in members:
                records_in_hour = sorted(per_hour[cpc, ptn, hour],
                                         key=lambda x: x.start)
                # Independently prove exact expected slot coverage.
                expected_starts = [DAY + dt.timedelta(hours=hour, minutes=m)
                                   for m in (0, 15, 30, 45)]
                if ([x.start for x in records_in_hour] != expected_starts or
                        any(x.duration_ms != 900000 for x in records_in_hour)):
                    break
                values.append(Fraction(sum(x.lac for x in records_in_hour), 4))
            if len(values) == len(members):
                cpc_hours[cpc, hour] = sum(values, Fraction())
    return unique, per_hour, cpc_hours


def verify(output, records, inventory):
    unique, per_hour, cpc_hours = oracle(records, inventory)
    actual_lp = {}
    actual_cpc = {}
    actual_peak = {}
    report_cpc = {}
    report_lp = {}
    current_cpc = None
    counts = None
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0].startswith('CPC='):
            current_cpc = bytes.fromhex(fields[0].split('=', 1)[1])
        if fields[0] in ('CPC_HOUR', 'LPAR_HOUR'):
            row = dict(field.split('=', 1) for field in fields[1:])
            hour = int(row['HOUR'].rsplit('/', 1)[-1])
            if fields[0] == 'CPC_HOUR':
                report_cpc[current_cpc, hour] = row
            else:
                report_lp[current_cpc, int(row['PTN']), hour] = row
        if fields[0] == 'CHECK_LPAR':
            actual_lp[fields[1], int(fields[2]), int(fields[3])] = (
                int(fields[4]), int(fields[5]))
        elif fields[0] == 'CHECK_CPC':
            actual_cpc[fields[1]] = (int(fields[2]), int(fields[3]))
        elif fields[0] == 'CHECK_PEAK':
            actual_peak[fields[1]] = (Fraction(fields[2]),
                                      int(fields[3].rsplit('/', 1)[-1]))
        elif fields[0] == 'CHECK_COUNTS':
            counts = tuple(map(int, fields[1:]))
    assert counts is not None, output
    assert counts[0] == len(unique), (counts, len(unique))
    for (cpc, ptn, hour), samples in per_hour.items():
        key = 'C' + cpc.hex().upper()
        assert actual_lp[key, ptn, hour] == (len(samples),
                                            sum(x.lac for x in samples))
        row = report_lp[cpc, ptn, hour]
        assert int(row['N']) == len(samples)
        if len(samples) == 4:
            assert row['STATUS'] == 'COMPLETE'
            assert Fraction(row['RAW_MEAN_MSU']) == Fraction(
                sum(x.lac for x in samples), 4)
        else:
            assert row['STATUS'] == 'INCOMPLETE'
            assert 'RAW_MEAN_MSU' not in row
    for cpc in {x[0] for x in inventory}:
        key = 'C' + cpc.hex().upper()
        hours = {hour: value for (candidate, hour), value in cpc_hours.items()
                 if candidate == cpc}
        assert actual_cpc[key] == (len(hours), 24 - len(hours))
        for hour in range(24):
            row = report_cpc[cpc, hour]
            assert int(row['EXPECTED_LPARS']) == sum(
                1 for candidate, _ in inventory if candidate == cpc)
            if hour in hours:
                assert row['STATUS'] == 'COMPLETE'
                assert Fraction(row['RAW_MSU']) == hours[hour]
            else:
                assert row['STATUS'] == 'INCOMPLETE'
                assert 'RAW_MSU' not in row
        if hours:
            peak = max(hours.values())
            earliest = min(hour for hour, value in hours.items() if value == peak)
            assert actual_peak[key] == (peak, earliest), (actual_peak[key], peak,
                                                         earliest)
        else:
            assert key not in actual_peak
    assert len(report_cpc) == 24 * len({x[0] for x in inventory})
    assert len(report_lp) == 24 * len(inventory)
    return counts, cpc_hours


def valid_case(name, records, inventory, **kwargs):
    output = run_case(name, records, inventory, **kwargs)
    verify(output, records, inventory)
    return output


# No parameters may imply a different metric without being rejected.
for name, args in [
    ('no_date', 'CPC=Y'),
    ('all_dates', 'CPC=Y DATE=*'),
    ('sid_filter', f'CPC=Y DATE={DAY_ARG} SID=SYSA'),
    ('hourly_disabled', f'CPC=Y DATE={DAY_ARG} HOURLY=N'),
    ('bad_cpc', f'CPC=YES DATE={DAY_ARG}'),
]:
    run_case(name, params=args, do_report=False, expected=12, contains='RC=12')


# Concurrent peak, independent CPCs, same SID on different physical sources.
inventory = [(CPC_A, 1), (CPC_A, 2), (CPC_B, 1)]
records = []
for hour, a, b, c in [(10, 100, 30, 200), (11, 50, 90, 70)]:
    records += sample_hour(CPC_A, 1, hour, [a]*4)
    records += sample_hour(CPC_A, 2, hour, [b]*4, sid='SYSB')
    records += sample_hour(CPC_B, 1, hour, [c]*4)
example = valid_case('concurrent_cross_cpc', records, inventory)
assert 'OBSERVED_COMPLETE_HOUR_PEAK' in example
report_lines = [line.rstrip() for line in example.splitlines()
                if not line.startswith('CHECK_')]
(WORK / 'cpc-example-report.txt').write_text('\n'.join(report_lines) + '\n',
                                            encoding='ascii')
for seed in (7, 83, 2026):
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    valid_case(f'order_{seed}', shuffled, inventory)
valid_case('reversed', list(reversed(records)), inventory)


# Full precision survives summing, and ties do not depend on input order.
fraction_records = []
for ptn in (1, 2):
    fraction_records += sample_hour(CPC_A, ptn, 10, [1, 1, 2, 2])
    fraction_records += sample_hour(CPC_A, ptn, 11, [1, 1, 2, 2])
valid_case('fraction_and_tie', list(reversed(fraction_records)),
           [(CPC_A, 1), (CPC_A, 2)])
precision_records = sample_hour(CPC_A, 1, 10, [2, 2, 3, 3])
precision_records += sample_hour(CPC_A, 1, 11, [2, 3, 3, 3])
valid_case('peak_before_rounding', precision_records, [(CPC_A, 1)])


# Four-hour averaging must not be repeated over the recorded LAC values.
valid_case('single_mean', sample_hour(CPC_A, 1, 10, [100, 120, 140, 160]),
           [(CPC_A, 1)])
valid_case('measured_zero', sample_hour(CPC_A, 1, 10, [0, 0, 0, 0]),
           [(CPC_A, 1)])
unsigned = []
for ptn in (1, 2):
    unsigned += sample_hour(CPC_A, ptn, 10, [4294967295]*4)
valid_case('unsigned_sum', unsigned, [(CPC_A, 1), (CPC_A, 2)])


# Missing members and missing entire hours remain visible from the map.
base = sample_hour(CPC_A, 1, 10, [100]*4)
partial = base + sample_hour(CPC_A, 2, 10, [200]*4)[:3]
valid_case('missing_interval', partial, [(CPC_A, 1), (CPC_A, 2)])
valid_case('missing_whole_lpar', base, [(CPC_A, 1), (CPC_A, 2)])
valid_case('missing_whole_cpc', base, [(CPC_A, 1), (CPC_B, 1)])
valid_case('empty_selected_day', [], [(CPC_A, 1)])
incomplete_peak = base + sample_hour(CPC_A, 1, 11, [999]*4)[:3]
valid_case('higher_incomplete_hour', incomplete_peak, [(CPC_A, 1)])


# Distinct equal values survive; actual duplicates/aliases count once.
dups = sample_hour(CPC_A, 1, 10, [12, 12, 28, 52])
dup_output = valid_case('duplicates_and_alias',
                       dups + [dups[0], replace(dups[1], sid='ALIS')],
                       [(CPC_A, 1)])
assert 'CHECK_COUNTS 4 2' in dup_output
run_case('duplicate_conflict', [dups[0], replace(dups[0], lac=13)],
         [(CPC_A, 1)], expected=12, contains='RC=12')
run_case('duplicate_wla_conflict', [dups[0], replace(dups[0], wla=999)],
         [(CPC_A, 1)], expected=12, contains='RC=12')


# Wholly invented end labels run from 06:00 through 07:00. A hypothetical
# report value of 45 is invented too; it does not define the raw oracle.
# All five labels must not be mistaken for one hour's four intervals.
five = [Sample(CPC_A, 1, DAY + dt.timedelta(hours=5, minutes=45 + 15*i), v)
        for i, v in enumerate([20, 60, 40, 80, 30])]
five_output = valid_case('five_values_midpoint', five, [(CPC_A, 1)])
assert ('CHECK_PEAK C' + CPC_A.hex().upper() +
        f' 52.5 {DAY_ARG}/06') in five_output
assert Fraction(sum([20, 60, 40, 80]), 4) == 50
assert Fraction(sum([20, 60, 40, 80, 30]), 5) == 46
valid_case('daymode_does_not_move_cpc_hour', five, [(CPC_A, 1)],
           params=DEFAULT + ' DAYMODE=START')


# Midnight is selected by the interval midpoint, including final23:45.
last = sample_hour(CPC_A, 1, 23, [10, 20, 30, 40])
outside = [replace(last[0], start=DAY - dt.timedelta(minutes=15)),
           replace(last[0], start=DAY + dt.timedelta(days=1))]
valid_case('midnight_selection', last + outside, [(CPC_A, 1)])


# Unsupported semantics fail explicitly: no interpolation or zero fill.
rejects = [
    ('five_minute', replace(dups[0], duration_ms=300000)),
    ('thirty_minute', replace(dups[0], duration_ms=1800000)),
    ('off_grid', replace(dups[0], start=dups[0].start + dt.timedelta(minutes=5))),
    ('off_grid_seconds', replace(dups[0], start=dups[0].start + dt.timedelta(seconds=1))),
    ('scope_off', replace(dups[0], scope=False)),
    ('blank_cpc', replace(dups[0], cpc=b' '*20)),
    ('null_cpc', replace(dups[0], cpc=b'\0'*20)),
    ('blank_plant', replace(dups[0], cpc=b' '*4 + CPC_A[4:])),
    ('blank_sequence', replace(dups[0], cpc=CPC_A[:4] + b' '*16)),
    ('blank_system', replace(dups[0], sysname=' '*8)),
    ('unmapped_partition', replace(dups[0], ptn=2)),
    ('unmapped_cpc', replace(dups[0], cpc=CPC_B)),
    ('hypervisor_offset', replace(dups[0], hof=1)),
    ('simplified_vm', replace(dups[0], inb=0x04)),
]
for name, sample in rejects:
    run_case(name, [sample], [(CPC_A, 1)], expected=12, contains='RC=12')


# N=4 and summed duration=60m cannot excuse an overlap/off-grid stream.
overlap = sample_hour(CPC_A, 1, 10, [100]*4)
overlap[-1] = replace(overlap[-1], start=DAY + dt.timedelta(hours=10, minutes=40))
run_case('coverage_overlap_trap', overlap, [(CPC_A, 1)], expected=12,
         contains='RC=12')
for name, changed in [
    ('offset_change', replace(dups[1], lgo=1)),
    ('system_change', replace(dups[1], sysname='OTHER')),
    ('sysplex_change', replace(dups[1], sysplex='OTHER')),
]:
    run_case(name, [dups[0], changed], [(CPC_A, 1)], expected=12,
             contains='RC=12')
run_case('different_lpar_offset',
         [dups[0], replace(dups[1], ptn=2, lgo=1)],
         [(CPC_A, 1), (CPC_A, 2)], expected=12, contains='RC=12')
valid_case('separate_cpc_offsets',
           sample_hour(CPC_A, 1, 10, [100]*4) +
           sample_hour(CPC_B, 1, 10, [200]*4, lgo=1),
           [(CPC_A, 1), (CPC_B, 1)])
valid_case('blank_sysplex_allowed',
           sample_hour(CPC_A, 1, 10, [100]*4, sysplex=' '*8),
           [(CPC_A, 1)])
valid_case('partition_number_boundaries',
           sample_hour(CPC_A, 0, 10, [100]*4) +
           sample_hour(CPC_A, 255, 10, [200]*4),
           [(CPC_A, 0), (CPC_A, 255)])


# Inventory is syntax-checked, unique, and supplies physical expectations.
for name, line in [
    ('map_short', 'ABCD 1'),
    ('map_nonhex', 'G'*40 + ' 1'),
    ('map_ptn_negative', CPC_A.hex().upper() + ' -1'),
    ('map_ptn_large', CPC_A.hex().upper() + ' 256'),
    ('map_ptn_text', CPC_A.hex().upper() + ' one'),
    ('map_extra_field', map_text(CPC_A, 1) + ' extra'),
]:
    run_case(name, raw_map=[line], do_report=False, expected=12,
             contains='RC=12')
run_case('map_duplicate', inventory=[(CPC_A, 1), (CPC_A, 1)],
         do_report=False, expected=12, contains='RC=12')
run_case('map_equivalent_duplicate', inventory=[(CPC_A, 1)],
         raw_map=[CPC_A.hex().lower() + ' 001'], do_report=False,
         expected=12, contains='RC=12')
run_case('empty_map_direct', expected=12, contains='RC=12')


# Mock only TSO commands; retain the real production top-level flow,
# CPCMAP parsing, final partial batches, CSV/report and exact exit path.
IO = """
fakeIo: procedure expose g. batch. map. out. rc
  parse arg command
  rc = 0
  dd = word(command,4)
  if pos('FINIS',command) > 0 then do
    rc = g.failClose.dd
    say 'IO_CLOSE' dd rc
    if dd = 'REPORT' then call cpcTestMetrics
    return
  end
  if word(command,3) = 'DISKR' then do
    if g.failRead.dd > 0 then do
      rc = g.failRead.dd
      return
    end
    amount = min(256,g.inputCount.dd-g.inputPos.dd)
    if dd = 'CPCMAP' then map.0 = amount
    else batch.0 = amount
    do n = 1 to amount
      g.inputPos.dd = g.inputPos.dd+1
      ix = g.inputPos.dd
      if dd = 'CPCMAP' then map.n = g.input.dd.ix
      else batch.n = g.input.dd.ix
    end
    if amount < 256 then rc = 2
    say 'IO_READ' dd amount rc
    return
  end
  if g.failWrite.dd > 0 then do
    rc = g.failWrite.dd
    return
  end
  say 'IO_WRITE' dd out.1
return

cpcTestMetrics: procedure expose g.
""" + METRICS + '\nreturn\n'


def main_case(name, records=(), inventory=(), *, map_lines=None,
              expected=0, setup='', contains=None):
    if map_lines is None:
        map_lines = [map_text(cpc, ptn) for cpc, ptn in inventory]
    lines = [f'g.inputCount.CPCMAP = {len(map_lines)}',
             f'g.inputCount.SMFIN = {len(records)}']
    lines.extend(f"g.input.CPCMAP.{i} = '{line}'"
                 for i, line in enumerate(map_lines, 1))
    lines.extend(f"g.input.SMFIN.{i} = x2c('{binary(item).hex()}')"
                 for i, item in enumerate(records, 1))
    lines.append(setup)
    source = SOURCE.replace('call initialize\n',
                            'call initialize\n' + '\n'.join(lines) + '\n', 1)
    source = source.replace('address TSO ', 'call fakeIo ')
    path = WORK / f'cpc_main_{name}.rexx'
    path.write_text(source + '\n' + IO, encoding='ascii')
    output = execute(path, DEFAULT + ' CSV=Y', expected=expected,
                     contains=contains)
    PASSED.append('main_' + name)
    return output


def verify_main(output, records, inventory):
    report = []
    csv_lines = []
    for line in output.splitlines():
        if line.startswith('IO_WRITE REPORT '):
            report.append(line.removeprefix('IO_WRITE REPORT '))
        elif line.startswith('IO_WRITE CSVOUT '):
            csv_lines.append(line.removeprefix('IO_WRITE CSVOUT '))
        elif line.startswith('CHECK_'):
            report.append(line)
    verify('\n'.join(report), records, inventory)
    parsed = list(csv.reader(csv_lines))
    assert parsed[0] == ['CPC_HEX', 'PTN', 'SID', 'START', 'END', 'HOUR',
                         'DURATION_MS', 'LAC_MSU', 'WLA_MSU', 'LGO_HEX',
                         'HOF_HEX', 'STF_BIT3', 'FLA_HEX', 'STF_HEX']
    unique, _, _ = oracle(records, inventory)
    assert len(parsed) == len(unique) + 1, (len(parsed), len(unique))
    expected = {}
    for _, sample in unique.values():
        expected[sample.cpc.hex().upper(), sample.ptn,
                 sample.start.strftime('%Y%j/%H:%M:%S.000')] = sample
    actual_keys = set()
    for row in parsed[1:]:
        assert len(row) == len(parsed[0]), row
        key = row[0], int(row[1]), row[3]
        assert key not in actual_keys
        actual_keys.add(key)
        sample = expected[key]
        assert row[2] == sample.sid
        assert row[4] == (sample.start + dt.timedelta(
            milliseconds=sample.duration_ms)).strftime('%Y%j/%H:%M:%S.000')
        assert row[5] == sample.start.strftime('%Y%j/%H')
        assert int(row[6]) == sample.duration_ms
        assert int(row[7]) == sample.lac
        assert int(row[8]) == sample.wla
        assert row[9] == sample.lgo.to_bytes(8, 'big').hex().upper()
        assert row[10] == sample.hof.to_bytes(8, 'big').hex().upper()
        assert row[11] == '1'
        assert row[12] == sample.flags.to_bytes(2, 'big').hex().upper()
        assert row[13] == '10'
    assert actual_keys == set(expected)
    for dd in ('CPCMAP', 'SMFIN', 'CSVOUT', 'REPORT'):
        assert f'IO_CLOSE {dd} 0' in output, dd


full_day = []
for hour in range(24):
    full_day += sample_hour(CPC_A, 1, hour, [100+hour]*4, wla=11)
    full_day += sample_hour(CPC_A, 2, hour, [50+2*hour]*4, sid='SYSB', wla=23)
    full_day += sample_hour(CPC_B, 1, hour, [200+3*hour]*4, wla=37)
full_inventory = [(CPC_A, 1), (CPC_A, 2), (CPC_B, 1)]
full_output = main_case('full_day_rc0', full_day, full_inventory)
verify_main(full_output, full_day, full_inventory)
assert 'IO_READ SMFIN 256 0' in full_output
assert 'IO_READ SMFIN 32 2' in full_output
assert 'FULL_DAY_PEAK_NOT_PROVEN' not in full_output

multi_map = ['# synthetic comment']*253 + [''] + [
    CPC_A.hex().lower() + ' 001', map_text(CPC_A, 2), map_text(CPC_B, 1)]
multi_output = main_case('map_final_batch', full_day, full_inventory,
                         map_lines=multi_map)
verify_main(multi_output, full_day, full_inventory)
assert 'IO_READ CPCMAP 256 0' in multi_output
assert 'IO_READ CPCMAP 1 2' in multi_output

duplicated_day = full_day[:256] + [full_day[0]] + full_day[256:]
duplicate_output = main_case('duplicate_across_batch_rc4', duplicated_day,
                             full_inventory, expected=4)
verify_main(duplicate_output, duplicated_day, full_inventory)
assert 'CHECK_COUNTS 288 1' in duplicate_output

missing_day = full_day[:-1]
missing_output = main_case('missing_slot_rc4', missing_day, full_inventory,
                           expected=4)
verify_main(missing_output, missing_day, full_inventory)
assert 'FULL_DAY_PEAK_NOT_PROVEN' in missing_output
empty_output = main_case('empty_day_rc4', [], [(CPC_A, 1)], expected=4)
verify_main(empty_output, [], [(CPC_A, 1)])
assert 'NO_COMPLETE_HOUR_PEAK' in empty_output
flagged_day = list(full_day)
flagged_day[0] = replace(flagged_day[0], flags=0x0060)
flagged_output = main_case('boost_warning_rc4', flagged_day, full_inventory,
                           expected=4)
verify_main(flagged_output, flagged_day, full_inventory)
assert 'INPUT_BOOST=1' in flagged_output

for name, setup, message in [
    ('map_read_fail', 'g.failRead.CPCMAP = 20', 'CPCMAP read failed RC=20'),
    ('map_empty_concat', 'g.failRead.CPCMAP = 4', 'CPCMAP read failed RC=4'),
    ('map_close_fail', 'g.failClose.CPCMAP = 20', 'CPCMAP close failed RC=20'),
    ('input_read_fail', 'g.failRead.SMFIN = 20', 'SMFIN read failed RC=20'),
    ('csv_truncation', 'g.failWrite.CSVOUT = 1', 'CSVOUT write failed RC=1'),
    ('csv_close_fail', 'g.failClose.CSVOUT = 20', 'CSVOUT close failed RC=20'),
    ('report_write_fail', 'g.failWrite.REPORT = 20', 'REPORT write failed RC=20'),
    ('report_close_fail', 'g.failClose.REPORT = 20', 'REPORT close failed RC=20'),
]:
    main_case(name, base, [(CPC_A, 1)], expected=12, setup=setup,
              contains=message)
main_case('empty_map', map_lines=['', '# no members'], expected=12,
          contains='CPCMAP has no expected LPARs')
main_case('conflicting_record_rc12', [dups[0], replace(dups[0], lac=999)],
          [(CPC_A, 1)], expected=12, contains='Conflicting CPC interval')


print(f'PASS: {len(PASSED)} CPC scenarios; physical identities, exact Fraction')
print('oracle, concurrent peaks, precision, coverage, duplicates, boundaries,')
print('map validation, input-order invariance and explicit unsupported cases;')
print('full-day RC0, incomplete/duplicate/flag RC4, conflict/I/O RC12, map/data')
print('batch EOF handling, CSV fields and all closes through the real entry.')
print('Not tested here: real SMF/EBCDIC/TSO, UTC conversion or IBM SCRT parity.')
