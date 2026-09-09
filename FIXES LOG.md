# FIXES LOG

Project owner: **Yarden Lechner**

## Possible corrections: what to check, what to change, and why

These are checks for a TSO/E REXX SMF 70-1 reader and its JCL.
Apply a correction only if the target code needs it. Most safeguards already
exist in the repository's R4HAMAX; the notes below also explain what to check
when adapting another implementation. This document contains no private
source, photographs, site identifiers or production measurements.

### 1. Apply the requested date as an actual filter

**Check:** Is the date argument used to select records, or only printed?

**Possible correction:** Validate YYYYDDD, derive the selected measurement day,
and reject other days before updating output, peaks or aggregates. Count
DATE exclusions separately from malformed records.

**Why:** A date in a dataset name or report heading does not restrict its
contents. A multi-day input can otherwise produce a peak from the wrong day.

### 2. Use RMF measurement time for the sample timestamp

**Check:** Does the reader use common SMF header time or the RMF interval?

**Possible correction:** Read Product-section SMF70DAT, SMF70IST and SMF70INT.
Calculate END = START + duration, handling milliseconds, midnight and year
rollover. Use one documented START/END policy for date selection and reporting.

**Why:** SMF recording time can differ from measurement time, causing a
comparison against the wrong interval or a wrong day near midnight.

### 3. Preserve I/O errors in the final return code

**Check:** Can a read/write/close error be replaced by a successful final RC?

**Possible correction:** Save EXECIO RC immediately. Process records returned
with EOF RC=2; treat other nonzero read codes as failures. Check output
truncation, writes and closes too. Preserve fatal RC=12 through cleanup,
even if earlier records were accepted. Mark partial output as unusable.

**Why:** A partial report must not look like a successful full-input result.
IKJEFT1B cannot recover a failure that the program itself replaces with RC=0.

### 4. Validate sections, producer and LAC scope

**Check:** Are section locations and semantics checked before field access?

**Possible correction:** Validate the consumed triplets, lengths, counts,
bounds and overlap against the supported IBM layout. Check producer and
collection mode. Detect RMF-level splitting through SMF70RAN and stop unless
reassembly is supported. Read STF bit 3 and report an off flag explicitly.

**Why:** An in-bounds binary number can still come from the wrong section or
an unsupported record. EXECIO VBS support does not reassemble RMF fragments.

### 5. Distinguish WLA capacity from LAC / R4HA

**Check:** Which field feeds the reported R4HA and the maximum calculation?

**Possible correction:** CPU Control relative offset 32 is SMF70WLA; offset
36 is SMF70LAC. Both are four bytes. In a string containing only that section:

```rexx
wla = C2D(Substr(ctlSection, 33, 4))
lac = C2D(Substr(ctlSection, 37, 4))
```

Use LAC for the recorded R4HA peak and label WLA separately as capacity.
For the whole RDW-free EXECIO string, the LAC position is CPU section offset
plus 36 minus 3. Do not subtract the RDW adjustment twice.

**Why:** Reporting capacity as R4HA produces plausible but wrong values.
A 15-minute record cadence is not a reason to divide recorded LAC by four.
[IBM CPU Control mapping](https://www.ibm.com/docs/en/zos/3.2.0?topic=s1cpia-cpu-control-section).

### 6. Retain the first sample even when its value is zero

**Check:** Is the maximum initialized to zero and updated only on greater-than?

**Possible correction:** Track whether a sample has been accepted per SID.
Store the first sample's value and timestamp even when LAC=0. Keep a stable
policy for later equal values.

**Why:** An all-zero day otherwise leaves the peak timestamp empty. Zero
consumption and no qualifying samples are different results.

### 7. Explain every exclusion

**Check:** Are records silently skipped, including by arbitrary MSU ceilings?

**Possible correction:** Add named rejection reasons and counters. Remove
undocumented value ceilings used instead of layout validation. Count normal
DATE/SID filtering separately, and investigate unexpected values explicitly.

**Why:** Silent exclusions can hide the true peak. Correct unsigned decoding
alone is not proof of a physically plausible measurement.

### 8. Bound memory used by input and output

**Check:** Does the program retain every input record or output row until EOF?

**Possible correction:** Read in batches and stream detail output. Retain only
state needed for peaks, requested aggregates and deduplication, with a documented
limit. R4HAMAX already reads batches of 256 and caps unique retained samples.

**Why:** A small daily test may pass while a larger dump exhausts storage.
Batching does not make total memory constant when history keys are retained.

### 9. Preserve previous output when a new run fails

**Check:** Does the JCL delete the previous report before the new run succeeds?

**Possible correction:** Use spool or distinct output datasets/GDG generations
under site policy. Accept new output only after checking the step RC. Do not
assume DISP=(NEW,CATLG,DELETE) discards output after a normal nonzero return.

**Why:** A failed rerun can otherwise destroy the earlier valid report and
leave a partial replacement. The repository jobs already default to spool.

### 10. Make DEBUG useful and bounded

**Check:** Does DEBUG display actual field evidence, or is the option only parsed?

**Possible correction:** Show sample SID/time, CPU section location/length,
WLA and LAC in HEX and decimal, and STF flags. Limit the number of records and
state which ones are shown. R4HAMAX now traces up to three unique selected
samples; these are not necessarily peak samples. DEBUG=N disables the trace.

**Why:** Raw bytes distinguish a wrong offset from a display or aggregation
problem. Plausible values alone cannot validate the parser. Keep real trace
output outside the public repository.

## Verification after any applicable correction

Check a multi-day input, midnight rollover, an all-zero day, distinct adjacent
WLA/LAC values, malformed sections, EOF with a partial batch and an I/O failure
after accepted records. Confirm separate SID results and unchanged arithmetic:
interval maximum and hourly sample mean are different outputs, neither is a
complete SCRT implementation. Use invented data for public regression tests.

Actual z/OS transfer, VBS I/O, complete-day coverage, independent field comparison
and scheduler return codes still require site validation. See the detailed
[acceptance plan](docs/TEST_PLAN.md) and [design](docs/DESIGN.md).
