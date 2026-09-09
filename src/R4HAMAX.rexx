/* REXX: R4HAMAX -- see README.md before submitting on z/OS. */
/* Author and project owner: Yarden Lechner. */
numeric digits 20
signal on syntax name failed
signal on novalue name failed
parse upper arg args
call initialize
if args = 'SELFTEST' then do
  call selftest
  exit 0
end
call parameters args
call readInput
call report
if g.validCnt = 0 then exit 4
if g.rejectCnt + g.scopeCnt + g.dupCnt > 0 then exit 4
if g.skippedCnt > 0 then exit 4
if g.boostCnt + g.convertedCnt + g.capacityCnt > 0 then exit 4
if g.weakCnt > 0 then exit 4
exit 0

initialize:
  g. = 0
  g.cfgDate = '*'
  g.cfgSid = '*'
  g.cfgTop = 10
  g.cfgMode = 'END'
  g.cfgHourly = 'Y'
  g.cfgDebug = 'N'
  g.cfgCsv = 'N'
  g.debugText = ''
  g.firstDate = ''
return

parameters: procedure expose g.
  parse arg args
  do pi = 1 to words(args)
    parse value word(args,pi) with pk '=' pv
    select
      when pk = 'DATE' then g.cfgDate = pv
      when pk = 'SID' then g.cfgSid = pv
      when pk = 'TOP' then g.cfgTop = pv
      when pk = 'DAYMODE' then g.cfgMode = pv
      when pk = 'HOURLY' then g.cfgHourly = pv
      when pk = 'DEBUG' then g.cfgDebug = pv
      when pk = 'CSV' then g.cfgCsv = pv
      otherwise call fatal 'Unknown parameter: 'word(args,pi)
    end
  end
  if g.cfgDate <> '*' then
    if validJul(g.cfgDate) = 0 then call fatal 'Bad DATE=YYYYDDD'
  if g.cfgSid <> '*' then do
    if length(g.cfgSid) < 1 | length(g.cfgSid) > 4 then
      call fatal 'SID must be 1 to 4 characters'
    if validSid(g.cfgSid) = 0 then
      call fatal 'SID allows A-Z, 0-9, #, @, $, and period'
  end
  if g.cfgTop = '' then call fatal 'Missing TOP'
  if verify(g.cfgTop,'0123456789') > 0 then call fatal 'Bad TOP'
  if g.cfgTop < 1 | g.cfgTop > 100 then call fatal 'TOP must be 1..100'
  if g.cfgMode <> 'END' & g.cfgMode <> 'START' then
    call fatal 'DAYMODE must be END or START'
  if g.cfgHourly <> 'Y' & g.cfgHourly <> 'N' then
    call fatal 'HOURLY must be Y or N'
  if g.cfgDebug <> 'Y' & g.cfgDebug <> 'N' then
    call fatal 'DEBUG must be Y or N'
  if g.cfgCsv <> 'Y' & g.cfgCsv <> 'N' then
    call fatal 'CSV must be Y or N'
return

readInput: procedure expose g.
  if g.cfgCsv = 'Y' then do
    call emit 'CSVOUT',,
      'SID,SAMPLE,START,END,DURATION_MS,LAC_MSU,STF_BIT3'
  end
  do forever
    batch. = ''
    address TSO 'EXECIO 256 DISKR SMFIN (STEM BATCH.'
    readRc = rc
    if readRc <> 0 & readRc <> 2 then do
      address TSO 'EXECIO 0 DISKR SMFIN (FINIS'
      call fatal 'SMFIN read failed RC='readRc
    end
    do bi = 1 to batch.0
      call process batch.bi
    end
    if readRc = 2 then leave
  end
  address TSO 'EXECIO 0 DISKR SMFIN (FINIS'
  if rc <> 0 then call fatal 'SMFIN close failed RC='rc
  if g.cfgCsv = 'Y' then do
    address TSO 'EXECIO 0 DISKW CSVOUT (FINIS'
    if rc <> 0 then call fatal 'CSVOUT close failed RC='rc
  end
return

/* Input is ONE logical record WITHOUT RDW, never a raw block. */
process: procedure expose g.
  parse arg rec
  g.readCnt = g.readCnt + 1
  if length(rec) < 2 then do
    call reject 'short'
    return
  end
  if uint(rec,5,1) <> 70 then return
  g.typeCnt = g.typeCnt + 1
  if length(rec) < 40 then do
    call reject 'short'
    return
  end
  if bitand(left(rec,1),'C0'x) \== 'C0'x then do
    call reject 'header'
    return
  end
  if uint(rec,22,2) <> 1 then return
  g.subCnt = g.subCnt + 1
  triplets = uint(rec,24,2)
  tableEnd = 28 + 8 * triplets
  if triplets < 2 | tableEnd > length(rec)+4 then do
    call reject 'triplet'
    return
  end
  po = uint(rec,28,4); pl = uint(rec,32,2)
  pn = uint(rec,34,2)
  co = uint(rec,36,4); cl = uint(rec,40,2)
  cn = uint(rec,42,2)
  if g.cfgDebug = 'Y' & g.debugText = '' then do
    g.debugText = 'LEN='length(rec) 'PRS='po pl pn 'CCS='co cl cn
    g.debugHex = c2x(left(rec,min(48,length(rec))))
  end
  if section(length(rec),po,pl,pn,104,tableEnd) = 0 then do
    call reject 'product'
    return
  end
  /* QSAM spanned-record assembly does not reassemble RMF records. */
  if uint(rec,po+74,2) <> 0 then
    call fatal 'SMF70RAN is nonzero; RMF reassembly is required'
  if section(length(rec),co,cl,cn,94,tableEnd) = 0 then do
    call reject 'cpu'
    return
  end
  if po < co+cl & co < po+pl then do
    call reject 'overlap'
    return
  end
  if substr(rec,18-3,4) \== 'RMF ' | ,
      strip(substr(rec,po+2-3,8)) \== 'RMF' then do
    call reject 'producer'
    return
  end
  fla = substr(rec,po+30-3,2)
  stf = substr(rec,co+5-3,1)
  /* Monitor I only: avoid mixing independent collection streams. */
  if bitand(left(fla,1),'20'x) \== '00'x then do
    call reject 'monitor3'
    return
  end
  /* Bit 1 says samples were skipped, NOT that LAC is invalid. */
  if bitand(left(fla,1),'40'x) \== '00'x then
    g.skippedCnt = g.skippedCnt + 1
  if bitand(right(fla,1),'60'x) \== '00'x then
    g.boostCnt = g.boostCnt + 1
  if bitand(left(fla,1),'0C'x) \== '00'x then
    g.convertedCnt = g.convertedCnt + 1
  if bitand(stf,'60'x) \== '00'x then
    g.capacityCnt = g.capacityCnt + 1
  dh = c2x(substr(rec,po+14-3,4))
  th = c2x(substr(rec,po+10-3,4))
  ih = c2x(substr(rec,po+18-3,4))
  decoded = decode(dh,th,ih)
  if decoded = '' then do
    call reject 'packed'
    return
  end
  parse var decoded jd ms dur
  sd = stamp(jd,ms)
  edate = jd; endms = ms + dur
  if endms >= 86400000 then do
    edate = nextDay(jd)
    endms = endms - 86400000
  end
  if validJul(edate) = 0 then do
    call reject 'packed'
    return
  end
  ed = stamp(edate,endms)
  sample = ed
  if g.cfgMode = 'START' then sample = sd
  if g.cfgDate <> '*' & left(sample,7) <> g.cfgDate then do
    g.dateCnt = g.dateCnt + 1
    return
  end
  sid = strip(substr(rec,14-3,4))
  if sid = '' then do
    call reject 'sid'
    return
  end
  if validSid(sid) = 0 then do
    call reject 'sid'
    return
  end
  if g.cfgSid <> '*' & sid \== g.cfgSid then do
    g.sidCnt = g.sidCnt + 1
    return
  end
  /* Compare raw identity/time-zone bytes, never a numeric string. */
  machine = substr(rec,co+74-3,20)
  names = substr(rec,po+88-3,16)
  ident = c2x(machine || substr(rec,po+50-3,1) || names)
  lgo = c2x(substr(rec,po+60-3,8))
  if strip(translate(machine,' ','00'x)) = '' | ,
      strip(translate(names,' ','00'x)) = '' then
    g.weakCnt = g.weakCnt + 1
  lac = uint(rec,co+36,4)
  scope = bitand(stf,'10'x) == '10'x
  call accept sid,sample,sd,ed,dur,lac,scope,ident,lgo
return

accept: procedure expose g.
  parse arg sid,sample,sd,ed,dur,lac,scope,ident,lgo
  sk = 'S'c2x(sid)
  if g.sidSamples.sk > 0 then do
    if g.identity.sk \== ident then
      call fatal 'Source identity changed for SID='sid
    if g.offset.sk \== lgo then
      call fatal 'GMT/local offset changed for SID='sid
  end
  else do
    g.identity.sk = ident
    g.offset.sk = lgo
  end
  dk = sk'.'sd'.'ed
  signature = lac':'scope
  if g.seen.dk <> 0 then do
    if g.seen.dk \== signature then
      call fatal 'Conflicting samples for SID='sid 'START='sd
    g.dupCnt = g.dupCnt + 1
    return
  end
  /* ponytail: bounded history; partition larger runs by day. */
  if g.validCnt >= 250000 then
    call fatal '250000 unique samples exceeded; split input by day'
  g.seen.dk = signature
  if g.sidSamples.sk = 0 then do
    g.sidCount = g.sidCount + 1
    si = g.sidCount; g.sidKey.si = sk
    g.sidName.sk = sid
  end
  if g.firstDate = '' then g.firstDate = left(sample,7)
  if left(sample,7) <> g.firstDate then g.multiDate = 1
  g.validCnt = g.validCnt + 1
  g.sidSamples.sk = g.sidSamples.sk + 1
  if scope = 0 then g.scopeCnt = g.scopeCnt + 1
  row = lac sample sd ed dur scope
  do ti = 1 to g.cfgTop
    if g.topRow.sk.ti = 0 then leave
    if lac > word(g.topRow.sk.ti,1) then leave
  end
  if ti <= g.cfgTop then do
    do tj = g.cfgTop to ti+1 by -1
      prev = tj-1
      g.topRow.sk.tj = g.topRow.sk.prev
    end
    g.topRow.sk.ti = row
  end
  if g.cfgHourly = 'Y' then do
    hk = sk'.'left(sample,10)
    if g.hourN.hk = 0 then do
      g.hourCount = g.hourCount + 1
      hi = g.hourCount; g.hourKey.hi = hk
      g.hourSid.hk = sid
      g.hourStamp.hk = left(sample,10)
      g.hourMinDur.hk = dur
      g.hourMaxDur.hk = dur
    end
    g.hourN.hk = g.hourN.hk + 1
    g.hourSum.hk = g.hourSum.hk + lac
    g.hourMax.hk = max(g.hourMax.hk,lac)
    g.hourMinDur.hk = min(g.hourMinDur.hk,dur)
    g.hourMaxDur.hk = max(g.hourMaxDur.hk,dur)
    if scope = 0 then g.hourScope.hk = g.hourScope.hk + 1
  end
  if g.cfgCsv = 'Y' then
    call emit 'CSVOUT',sid','sample','sd','ed','dur','lac','scope
return

validSid: procedure
  parse arg sid
  if length(sid) < 1 | length(sid) > 4 then return 0
return verify(sid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$.') = 0

reject: procedure expose g.
  parse upper arg reason
  g.rejectCnt = g.rejectCnt + 1
  g.bad.reason = g.bad.reason + 1
return

/* Decimal offsets include the RDW. Section offsets use same origin. */
uint: procedure
  parse arg rec,offset,size
return x2d(c2x(substr(rec,offset-3,size)))

section: procedure
  parse arg rl,so,sl,sn,minimum,tableEnd
  /* Product and CPU control are singleton sections in this mapping. */
  if sn <> 1 | sl < minimum | so < tableEnd then return 0
  if so+sl > rl+4 then return 0
return 1

positivePacked: procedure
  parse arg hx
  if length(hx) <> 8 then return 0
  if verify(left(hx,7),'0123456789') > 0 then return 0
  /* IBM documents F. C is accepted as a positive packed sign. */
  if right(hx,1) <> 'F' & right(hx,1) <> 'C' then return 0
return 1

decode: procedure
  parse arg dh,th,ih
  if positivePacked(dh) = 0 then return ''
  if positivePacked(th) = 0 then return ''
  if positivePacked(ih) = 0 then return ''
  if left(dh,1) <> '0' | left(th,1) <> '0' then return ''
  yr = 1900 + substr(dh,2,3)
  jd = yr || substr(dh,5,3)
  if validJul(jd) = 0 then return ''
  hh = substr(th,2,2); mm = substr(th,4,2)
  ss = substr(th,6,2)
  if hh > 23 | mm > 59 | ss > 59 then return ''
  im = left(ih,2); isec = substr(ih,3,2)
  ims = substr(ih,5,3)
  if isec > 59 then return ''
  ms = ((hh*60+mm)*60+ss)*1000
  dur = (im*60+isec)*1000+ims
  if dur = 0 then return ''
return jd ms dur

daysInYear: procedure
  parse arg yr
  leap = (yr//4 = 0) & ((yr//100 <> 0) | (yr//400 = 0))
return 365+leap

validJul: procedure
  parse arg jd
  if length(jd) <> 7 then return 0
  if verify(jd,'0123456789') > 0 then return 0
  yr = left(jd,4); dy = right(jd,3)
  if yr < 1900 | yr > 2899 then return 0
  if dy < 1 | dy > daysInYear(yr) then return 0
return 1

nextDay: procedure
  parse arg jd
  yr = left(jd,4); dy = right(jd,3)+1
  if dy > daysInYear(yr) then do
    yr = yr+1; dy = 1
  end
return yr || right(dy,3,'0')

stamp: procedure
  parse arg jd,ms
  hh = ms%3600000
  mm = (ms//3600000)%60000
  ss = (ms//60000)%1000
return jd'/'right(hh,2,'0')':'right(mm,2,'0')':' ||,
  right(ss,2,'0')'.'right(ms//1000,3,'0')

report: procedure expose g.
  call emit 'REPORT','R4HAMAX - recorded interval R4HA peak (MSU)'
  call emit 'REPORT','DATE='g.cfgDate 'SID='g.cfgSid ||,
    ' DAYMODE='g.cfgMode 'TOP='g.cfgTop
  call emit 'REPORT','Timestamps: YYYYDDD/HH:MM:SS.mmm, RMF local time'
  if g.validCnt = 0 then call emit 'REPORT','NO QUALIFYING SAMPLES'
  do ri = 1 to g.sidCount
    sk = g.sidKey.ri
    call emit 'REPORT',' '
    call emit 'REPORT','SID='g.sidName.sk ||,
      ' UNIQUE_SAMPLES='g.sidSamples.sk
    call emit 'REPORT','RANK MSU SAMPLE START END DURATION_MS STF_BIT3'
    do rj = 1 to g.cfgTop
      if g.topRow.sk.rj = 0 then leave
      call emit 'REPORT',rj g.topRow.sk.rj
    end
    if word(g.topRow.sk.1,6) = 0 then
      call emit 'REPORT','WARNING: peak STF bit 3 OFF; check scope'
  end
  if g.sidCount > 1 then
    call emit 'REPORT','Multiple SIDs: separate peaks, NO CPC sum'
  if g.multiDate = 1 then
    call emit 'REPORT','Multiple sample dates selected'
  if g.cfgHourly = 'Y' then do
    call emit 'REPORT',' '
    call emit 'REPORT','HOURLY SAMPLE MEANS - NOT SCRT / NOT COVERAGE'
    call emit 'REPORT','SID HOUR N MEAN_MSU MAX_MSU MIN_MS MAX_MS OFF'
    do hi = 1 to g.hourCount
      hk = g.hourKey.hi
      avg = g.hourSum.hk / g.hourN.hk
      call emit 'REPORT',g.hourSid.hk g.hourStamp.hk ||,
        ' 'g.hourN.hk format(avg,,3) g.hourMax.hk ||,
        ' 'g.hourMinDur.hk g.hourMaxDur.hk g.hourScope.hk
      hsk = 'S'c2x(g.hourSid.hk)
      if g.bestHour.hsk = 0 then g.bestHour.hsk = hk
      bestKey = g.bestHour.hsk
      if avg > g.hourSum.bestKey/g.hourN.bestKey then
        g.bestHour.hsk = hk
    end
    do hi = 1 to g.sidCount
      hsk = g.sidKey.hi; hk = g.bestHour.hsk
      call emit 'REPORT','PEAK_HOURLY_MEAN SID='g.sidName.hsk ||,
        ' HOUR='g.hourStamp.hk ||,
        ' MSU='format(g.hourSum.hk/g.hourN.hk,,3)
    end
    call emit 'REPORT','Means use sample hour per DAYMODE; no weights'
    call emit 'REPORT','No gap filling; unequal durations need review'
  end
  call emit 'REPORT',' '
  call emit 'REPORT','READ='g.readCnt 'TYPE70='g.typeCnt ||,
    ' SUB1='g.subCnt 'VALID='g.validCnt
  call emit 'REPORT','DATE_FILTER='g.dateCnt 'SID_FILTER='g.sidCnt
  call emit 'REPORT','REJECTED='g.rejectCnt ||,
    ' DUPLICATES='g.dupCnt 'STF_OFF='g.scopeCnt
  call emit 'REPORT','INPUT_RECORDS_WITH_SKIPPED_SAMPLES='g.skippedCnt
  call emit 'REPORT','INPUT_BOOST='g.boostCnt ||,
    ' INPUT_CONVERTED='g.convertedCnt
  call emit 'REPORT','INPUT_CAPACITY_CHANGE='g.capacityCnt ||,
    ' SELECTED_WEAK_IDENTITY='g.weakCnt
  call emit 'REPORT','Recorded LAC only; check IPL warm-up and gaps'
  reasons = 'SHORT HEADER TRIPLET PRODUCT CPU OVERLAP PACKED SID'
  reasons = reasons 'PRODUCER MONITOR3'
  do di = 1 to words(reasons)
    reason = word(reasons,di)
    call emit 'REPORT','REJECT_'translate(reason)'='g.bad.reason
  end
  if g.cfgDebug = 'Y' & g.debugText <> '' then do
    call emit 'REPORT','DEBUG 'g.debugText
    call emit 'REPORT','DEBUG HEX 'g.debugHex
  end
  if g.testing = 1 then return
  address TSO 'EXECIO 0 DISKW REPORT (FINIS'
  if rc <> 0 then call fatal 'REPORT close failed RC='rc
return

emit: procedure expose g.
  parse arg dd,text
  if g.testing = 1 then do
    g.outputCnt = g.outputCnt+1
    oi = g.outputCnt; g.output.oi = text
    return
  end
  out.1 = text
  address TSO 'EXECIO 1 DISKW' dd '(STEM OUT.'
  if rc <> 0 then do
    say text
    call fatal dd 'write failed RC='rc
  end
return

fatal:
  parse arg message
  say 'R4HAMAX ERROR:' message
  say 'RC=12. Discard partial REPORT/CSVOUT; correct and rerun.'
exit 12

failed:
  say 'R4HAMAX REXX condition:' condition('C') 'at line' sigl
  say condition('D')
  say 'RC=12. Discard partial output.'
exit 12

/* Synthetic records exercise the SAME parser used by EXECIO. */
selftest:
  g.testing = 1
  call check daysInYear(2000)=366,'leap 2000'
  call check daysInYear(2100)=365,'century 2100'
  call check validJul('2026366')=0,'invalid Julian day'
  call check nextDay('2024366')='2025001','year rollover'
  call check decode('0126251F','0235900F','0100000F') <> '',,
    'packed decode'
  call check decode('0126251D','0000000F','1500000F') = '',,
    'negative date'
  call check decode('0126251F','0240000F','1500000F') = '',,
    'invalid time'
  call check decode('0126251F','0000000F','1560000F') = '',,
    'invalid interval'
  call check decode('0126251F','0000000F','0000000F') = '',,
    'zero interval'
  call parameters 'TOP=2 SID=SYSA DATE=2026251 DAYMODE=END'
  a = fixture('SYSA','0126251F','0100000F','1500000F',100,1)
  call process a
  call process a
  a = fixture('SYSA','0126251F','0101500F','1500000F',160,0)
  call process a
  a = fixture('SYSA','0126251F','0103000F','1500000F',130,1)
  call process a
  sk = 'S'c2x('SYSA')
  call check g.validCnt=3,'valid records'
  call check g.dupCnt=1,'deduplicate'
  call check word(g.topRow.sk.1,1)=160,'peak'
  call check word(g.topRow.sk.2,1)=130,'top order'
  call check g.scopeCnt=1,'scope flag'
  hk = sk'.2026251/10'
  call check g.hourN.hk=3,'hour count'
  call check g.hourSum.hk/g.hourN.hk=130,'hour mean'
  a = fixture('SYSB','0126251F','0100000F','1500000F',999,1)
  call process a
  call check g.sidCnt=1,'SID filter'
  a = fixture('SYSA','0126250F','0234500F','1500000F',200,1)
  call process a
  call check word(g.topRow.sk.1,2)='2026251/00:00:00.000',,
    'midnight END selection'
  g.cfgMode = 'START'
  call process a
  call check g.dateCnt=1,'START selection'
  g.cfgMode = 'END'
  a = fixture('SYSA','0126251F','0100000F','1500000F',100,1)
  call process left(a,39)
  call check g.bad.short=1,'short record'
  call process overlay(d2c(99999,4),a,36-3,4)
  call check g.bad.cpu=1,'section out of bounds'
  call process overlay(d2c(2,2),a,42-3,2)
  call check g.bad.cpu=2,'non-singleton section'
  call process overlay('40'x,a,44+30-3,1)
  call check g.skippedCnt=1,'skipped RMF samples warning'
  call process overlay('0126251D'x,a,44+14-3,4)
  call check g.bad.packed=1,'bad packed record'
  call report
  call check g.outputCnt>10,'report built'
  say 'SELFTEST PASS: parser, bounds, flags, dates, filters,'
  say 'deduplication, Top-N, hourly mean and report.'
return

check:
  parse arg truth,label
  if truth <> 1 then call fatal 'SELFTEST failed: 'label
return

fixture: procedure
  parse arg sid,dh,th,ih,lac,scope
  /* RDW-relative: header 44, product 104, CPU 94 = 242 bytes. */
  rec = copies('00'x,238)
  rec = overlay('C0'x,rec,1,1)
  rec = overlay(d2c(70,1),rec,5-3,1)
  rec = overlay(left(sid,4),rec,14-3,4)
  rec = overlay('RMF ',rec,18-3,4)
  rec = overlay(d2c(1,2),rec,22-3,2)
  rec = overlay(d2c(2,2),rec,24-3,2)
  rec = overlay(d2c(44,4),rec,28-3,4)
  rec = overlay(d2c(104,2),rec,32-3,2)
  rec = overlay(d2c(1,2),rec,34-3,2)
  rec = overlay(d2c(148,4),rec,36-3,4)
  rec = overlay(d2c(94,2),rec,40-3,2)
  rec = overlay(d2c(1,2),rec,42-3,2)
  rec = overlay(left('RMF',8),rec,44+2-3,8)
  rec = overlay(left('TESTPLEX',8),rec,44+88-3,8)
  rec = overlay(left(sid,8),rec,44+96-3,8)
  rec = overlay(x2c(th),rec,44+10-3,4)
  rec = overlay(x2c(dh),rec,44+14-3,4)
  rec = overlay(x2c(ih),rec,44+18-3,4)
  rec = overlay(d2c(scope*16,1),rec,148+5-3,1)
  rec = overlay(d2c(lac,4),rec,148+36-3,4)
  rec = overlay('TEST0000000000000001',rec,148+74-3,20)
return rec
