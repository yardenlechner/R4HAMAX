"""Run real REXX logic; mock only TSO EXECIO for desktop I/O checks.

Usage: python tests/run_checks.py /path/to/regina
No Python packages required. No real SMF data is read or generated.
"""
from pathlib import Path
import datetime as dt
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

def run(path, args='', ok=True, contains=''):
    p = subprocess.run([REXX, str(path), args], capture_output=True,
                       text=True, timeout=30)
    assert (p.returncode == 0) == ok, (args, p.returncode, p.stdout, p.stderr)
    assert contains in p.stdout, (args, contains, p.stdout, p.stderr)
    return p.stdout

def driver(name, body, io=''):
    # The entire production file is retained; only its entry and TSO I/O
    # statements change. Parser/date/selection/aggregation stay untouched.
    source = SOURCE.replace('call initialize\n',
                            'call initialize\ncall scenario\nexit 0\n', 1)
    if io:
        source = source.replace('address TSO ', 'call fakeIo ')
    path = WORK / (name + '.rexx')
    path.write_text(source + '\nscenario:\n' + body + '\nreturn\n' + io,
                    encoding='ascii')
    return path

print(run(ROOT / 'src/R4HAMAX.rexx', 'SELFTEST').strip())
for args in ['TOP=0', 'TOP=1.5', 'TOP=101', 'DATE=2026366',
             'DATE=2026+01', 'SID=A,B', 'DAYMODE=X', 'CSV=YES',
             'HOURLY=', 'DEBUG=X', 'UNKNOWN=Y']:
    run(ROOT / 'src/R4HAMAX.rexx', args, ok=False, contains='RC=12')

# Independent Gregorian oracle, including non-leap century boundaries.
body = []
for year in [1900, 1999, 2000, 2024, 2026, 2099, 2100, 2399, 2400, 2898]:
    for month, day in [(2, 28), (3, 1), (12, 31)]:
        date = dt.date(year, month, day)
        jd = date.strftime('%Y%j')
        nxt = (date + dt.timedelta(days=1)).strftime('%Y%j')
        body.append(f"call check nextDay('{jd}')='{nxt}','calendar {jd}'")
body += ["call check stamp('2026251',86399999) = ,",
         "  '2026251/23:59:59.999','milliseconds'",
         "say 'CALENDAR PASS'"]
run(driver('calendar', '\n'.join(body)), contains='CALENDAR PASS')

# Conflicting duplicates must abort instead of silently averaging.
body = """
g.testing = 1
a = fixture('SYSA','0126251F','0100000F','1500000F',100,1)
call process a
call process overlay(d2c(101,4),a,148+36-3,4)
"""
run(driver('conflict', body), ok=False, contains='Conflicting samples')

# Check SID separation, zero/unsigned values, ties, all dates and debug.
body = """
g.testing = 1
call parameters 'TOP=2 DEBUG=Y'
call process fixture('SYSA','0126251F','0100000F','1500000F',0,1)
call process fixture('SYSB','0126251F','0100000F','1500000F',4294967295,1)
call process fixture('SYSA','0126251F','0110000F','1500000F',0,1)
call process fixture('SYSA','0126252F','0100000F','1500000F',0,1)
ka = 'S'c2x('SYSA'); kb = 'S'c2x('SYSB')
call check g.sidCount=2,'two SIDs'
call check word(g.topRow.ka.1,1)=0,'zero is valid'
call check word(g.topRow.kb.1,1)=4294967295,'unsigned 32-bit'
call check word(g.topRow.ka.1,2)='2026251/10:15:00.000','stable tie'
call check g.multiDate=1,'multiple dates'
call check g.debugText <> '', 'debug map'
call report
say 'MULTISID PASS'
"""
run(driver('multisid', body), contains='MULTISID PASS')

body = """
g.testing = 1
call process fixture('0','0126251F','0100000F','1500000F',0,1)
call process fixture('0','0126251F','0110000F','1500000F',0,1)
call check g.sidCount=1,'numeric zero SID stays one system'
call report
say 'ZERO SID PASS'
"""
run(driver('zerosid', body), contains='ZERO SID PASS')

# IBM SMFPRMxx permits national characters and periods in SIDs.
body = """
g.testing = 1
call parameters 'SID=#@$. TOP=1'
call process fixture('#@$.','0126251F','0100000F','1500000F',17,1)
call check g.validCnt=1,'national characters in SID'
call check g.sidCount=1,'punctuation is safe in stem keys'
say 'SID CHARACTERS PASS'
"""
run(driver('national_sid', body), contains='SID CHARACTERS PASS')

# Distinct adjacent WLA/LAC values must never be interchanged.
body = """
g.testing = 1
call parameters 'DATE=2018001 DEBUG=Y'
a = fixture('SYSA','0118001F','0000000F','1500000F',12,1)
a = overlay('000000490000000C'x,a,148+32-3,8)
call process a
call process a
sk = 'S'c2x('SYSA')
call check word(g.topRow.sk.1,1)=12,'LAC not WLA'
call check pos('WLA_HEX=00000049 WLA=73',g.debugField.1)>0, ,
  'WLA diagnostic'
call check pos('LAC_HEX=0000000C LAC=12',g.debugField.1)>0, ,
  'LAC diagnostic'
call process fixture('SYSA','0118002F','0000000F','1500000F',99,1)
call check g.debugCount=1,'duplicates and filtered samples omitted'
do n = 1 to 4
  a = fixture('SYSB','0118001F','0000000F','1500000F',9,1)
  a = overlay('0000003A00000009'x,a,148+32-3,8)
  a = overlay(x2c('0000'right(n,2,'0')'0F'),a,44+10-3,4)
  call process a
end
call check g.debugCount=3,'three sample diagnostic limit'
sk = 'S'c2x('SYSB')
call check word(g.topRow.sk.1,1)=9,'second SID LAC not WLA'
call check pos('WLA=58',g.debugField.2)>0,'second SID WLA'
call report
found = 0
do n = 1 to g.outputCnt
  if pos('DEBUG FIELDS WLA_HEX=00000049',g.output.n)>0 then
    found = 1
end
call check found=1,'field diagnostic reaches report'
call initialize
g.testing = 1
call process fixture('SYSA','0118001F','0000000F','1500000F',0,1)
call check g.debugCount=0,'debug disabled by default'
say 'WLA/LAC DEBUG PASS'
"""
run(driver('wla_lac_debug', body), contains='WLA/LAC DEBUG PASS')

# Independent Python byte construction, using published IBM sample
# boundaries: nine triplets, product at 100/104, CPU at 204/344.
# Text uses the desktop interpreter's ASCII, not a raw EBCDIC dump.
record = bytearray(544)
def put(offset, value):
    record[offset-4:offset-4+len(value)] = value
put(4, b'\xc0\x46')
put(14, b'SYSA')
put(18, b'RMF ')
put(22, struct.pack('>HH', 1, 9))
put(28, struct.pack('>IHHIHH', 100, 104, 1, 204, 344, 1))
put(102, b'RMF     ')
put(110, bytes.fromhex('0235959F0126365F0000001F'))
put(188, b'TESTPLEXSYSA    ')
put(209, b'\x10')
put(240, struct.pack('>I', 123456))
put(278, b'TEST0000000000000001')
body = f"""
g.testing = 1
a = x2c('{record.hex()}')
call process a
sk = 'S'c2x('SYSA')
call check g.validCnt=1,'independent IBM layout'
call check word(g.topRow.sk.1,1)=123456,'relocated LAC'
call check word(g.topRow.sk.1,2)='2026365/23:59:59.001','1 ms'
say 'INDEPENDENT LAYOUT PASS'
"""
run(driver('ibm_layout', body), contains='INDEPENDENT LAYOUT PASS')

# Reject malformed/unintended inputs instead of interpreting padded
# SUBSTR bytes or combining Monitor I and Monitor III measurements.
body = """
g.testing = 1
a = fixture('SYSA','0126251F','0100000F','1500000F',100,1)
do n = 2 to length(a)-1
  call process left(a,n)
end
call check g.validCnt=0,'all record truncations rejected'
call initialize
g.testing = 1
call process overlay('00'x,a,1,1)
call check g.bad.HEADER=1,'header format flags'
call process overlay('CMF ',a,18-3,4)
call check g.bad.PRODUCER=1,'non-RMF subsystem'
call process overlay('CMF     ',a,44+2-3,8)
call check g.bad.PRODUCER=2,'non-RMF product'
call process overlay('20'x,a,44+30-3,1)
call check g.bad.MONITOR3=1,'Monitor III excluded'
call process overlay(d2c(0,2),a,24-3,2)
call check g.bad.TRIPLET=1,'too few triplets'
call process overlay(d2c(999,2),a,24-3,2)
call check g.bad.TRIPLET=2,'triplets outside record'
call process overlay(d2c(44,4),a,36-3,4)
call check g.bad.OVERLAP=1,'overlapping sections'
call process overlay(d2c(103,2),a,32-3,2)
call check g.bad.PRODUCT=1,'short product section'
call process overlay(d2c(93,2),a,40-3,2)
call check g.bad.CPU=1,'short CPU identity'
call process overlay('4060'x,a,44+30-3,2)
call process overlay('0C'x,a,44+30-3,1)
call process overlay('70'x,a,148+5-3,1)
call check g.validCnt=1,'flag-only variants deduplicated'
call check g.skippedCnt=1,'samples skipped retained'
call check g.boostCnt=1,'boost warning'
call check g.convertedCnt=1,'conversion warning'
call check g.capacityCnt=1,'capacity change warning'
say 'GUARDS PASS'
"""
run(driver('guards', body), contains='GUARDS PASS')

base = """
g.testing = 1
a = fixture('SYSA','0126251F','0100000F','1500000F',100,1)
"""
for name, body, message in [
    ('broken', "call process overlay(d2c(1,2),a,44+74-3,2)",
     'RMF reassembly is required'),
    ('unknown_ran', "call process overlay(d2c(2,2),a,44+74-3,2)",
     'RMF reassembly is required'),
    ('identity', "call process a\n"
     "call process overlay('OTHER   ',a,44+96-3,8)",
     'Source identity changed'),
    ('machine', "call process a\n"
     "call process overlay('OTHERPLANT00000000002',a,148+74-3,20)",
     'Source identity changed'),
    ('timezone', "call process a\n"
     "call process overlay(d2c(1,8),a,44+60-3,8)",
     'GMT/local offset changed'),
    ('sample_limit', "g.validCnt=250000\ncall process a",
     '250000 unique samples exceeded'),
]:
    run(driver(name, base + body), ok=False, contains=message)

body = base + """
call process overlay(copies('00'x,20),a,148+74-3,20)
call check g.weakCnt=1,'missing identity warning'
call check g.validCnt=1,'weak identity value retained'
say 'WEAK IDENTITY PASS'
"""
run(driver('weak_identity', body), contains='WEAK IDENTITY PASS')

# Simulate two EXECIO batches (256 and 2 records), EOF RC=2 with data,
# CSV/report writes, and close calls. Includes one duplicate.
io = """
fakeIo: procedure expose g. batch. out. rc
  parse arg command
  rc = 0
  if pos('DISKR SMFIN',command) > 0 then do
    if pos('FINIS',command) > 0 then do
      if g.failClose = 1 then rc = 20
      g.inputClosed = 1
      return
    end
    if g.failRead = 1 then do
      rc = 20
      return
    end
    if g.emptyConcat = 1 then do
      rc = 4
      return
    end
    g.batches = g.batches + 1
    leftCount = g.inputCount-g.inputPos
    batch.0 = min(256,leftCount)
    do n = 1 to batch.0
      g.inputPos = g.inputPos+1
      ix = g.inputPos
      batch.n = g.input.ix
    end
    if batch.0 < 256 then rc = 2
    return
  end
  parse var command . . . dd .
  if pos('FINIS',command) > 0 then do
    if g.failClose = 1 then rc = 20
    g.closed.dd = 1
    return
  end
  if g.failWrite = 1 then do
    rc = 20
    return
  end
  if g.truncateWrite = 1 then do
    rc = 1
    return
  end
  g.written.dd = g.written.dd+1
  ix = g.written.dd
  g.lines.dd.ix = out.1
return
"""
body = """
call parameters 'CSV=Y TOP=3'
do n = 1 to 257
  tm = '010'right((n-1)%60,2,'0')right((n-1)//60,2,'0')'F'
  g.input.n = fixture('SYSA','0126251F',tm,'1500000F',n-1,1)
end
g.input.258 = g.input.1
g.inputCount = 258
call readInput
call report
call check g.batches=2,'two batches'
call check g.readCnt=258,'all records'
call check g.validCnt=257,'final partial batch processed'
call check g.dupCnt=1,'duplicate dropped before CSV'
call check g.written.CSVOUT=258,'CSV header plus unique samples'
call check left(g.lines.CSVOUT.1,10)='SID,SAMPLE','CSV header'
call check left(g.lines.CSVOUT.2,5)='SYSA,','CSV sample'
call check g.closed.CSVOUT=1,'CSV closed'
call check g.closed.REPORT=1,'REPORT closed'
call check g.inputClosed=1,'input closed'
say 'IO PASS'
"""
run(driver('io', body, io), contains='IO PASS')
for name, body, message in [
    ('readfail', 'g.failRead = 1\ncall readInput', 'SMFIN read failed'),
    ('writefail', "g.failWrite = 1\ncall emit 'REPORT','test'", 'write failed'),
    ('truncate', "g.truncateWrite = 1\ncall emit 'REPORT','test'",
     'write failed RC=1'),
    ('concat', 'g.emptyConcat = 1\ncall readInput', 'SMFIN read failed RC=4'),
    ('closefail', 'g.failClose = 1\ncall readInput', 'SMFIN close failed'),
]:
    run(driver(name, body, io), ok=False, contains=message)

# Exercise the real top-level return-code decision, with just I/O mocked.
for name, setup, expected in [
    ('empty_rc', '', 4),
    ('normal_rc', "g.inputCount=1\ng.input.1="
     "fixture('SYSA','0126251F','0100000F','1500000F',100,1)", 0),
    ('scope_rc', "g.inputCount=1\ng.input.1="
     "fixture('SYSA','0126251F','0100000F','1500000F',100,0)", 4),
]:
    main = SOURCE.replace('call initialize\n',
                          'call initialize\n' + setup + '\n', 1)
    main = main.replace('address TSO ', 'call fakeIo ')
    path = WORK / (name + '.rexx')
    path.write_text(main + '\n' + io, encoding='ascii')
    result = subprocess.run([REXX, str(path)], capture_output=True,
                            text=True, timeout=30)
    # Regina Windows normalizes nonzero EXIT to process RC 1; Unix
    # preserves the REXX RC. Either must remain a failure, never zero.
    assert (result.returncode == 0) == (expected == 0), result
run(driver('empty', "g.testing = 1\ncall readInput\ncall report\n"
           "call check g.validCnt=0,'empty input'\nsay 'EMPTY PASS'", io),
    contains='EMPTY PASS')

# A reproducible example from actual report code, with synthetic data.
body = """
g.testing = 1
call parameters 'DATE=2026251 SID=SYSA TOP=3'
call process fixture('SYSA','0126251F','0100000F','1500000F',100,1)
call process fixture('SYSA','0126251F','0101500F','1500000F',160,1)
call process fixture('SYSA','0126251F','0103000F','1500000F',130,1)
call report
do n = 1 to g.outputCnt
  say g.output.n
end
"""
example = run(driver('example', body), contains='MSU=130.000')
example = '\n'.join(line.rstrip() for line in example.splitlines()) + '\n'
(WORK / 'example-report.txt').write_text(example, encoding='ascii')

for path in [ROOT / 'src/R4HAMAX.rexx', *ROOT.glob('jcl/*.jcl')]:
    for n, line in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        assert len(line) <= 72, (path.name, n, len(line))
print('PASS: parameters, calendar oracle, conflicts, multi-SID, unsigned,')
print('batch/EOF I/O simulation, failures, empty input, report and columns.')
print('PASS: IBM layout, truncation sweep, SID characters, producer/flags,')
print('RMF splitting, identity/time-zone guards, I/O errors and limits.')
print('Not tested here: z/OS EXECIO/QSAM, EBCDIC transfer, JCL submission.')
