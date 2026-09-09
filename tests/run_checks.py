"""Run real REXX logic; mock only TSO EXECIO for desktop I/O checks.

Usage: python tests/run_checks.py /path/to/regina
No Python packages required. No real SMF data is read or generated.
"""
from pathlib import Path
import datetime as dt
import shutil
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
call process overlay(d2c(101,4),a,76+36-3,4)
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
call check words(g.ids)=2,'two SIDs'
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
call check words(g.ids)=1,'numeric zero SID stays one system'
call report
say 'ZERO SID PASS'
"""
run(driver('zerosid', body), contains='ZERO SID PASS')

# Simulate two EXECIO batches (256 and 2 records), EOF RC=2 with data,
# CSV/report writes, and close calls. Includes one duplicate.
io = """
fakeIo: procedure expose g. batch. out. rc
  parse arg command
  rc = 0
  if pos('DISKR SMFIN',command) > 0 then do
    if pos('FINIS',command) > 0 then do
      g.inputClosed = 1
      return
    end
    if g.failRead = 1 then do
      rc = 20
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
    g.closed.dd = 1
    return
  end
  if g.failWrite = 1 then do
    rc = 20
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
]:
    run(driver(name, body, io), ok=False, contains=message)
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
print('Not tested here: z/OS EXECIO/QSAM, EBCDIC transfer, JCL submission.')
