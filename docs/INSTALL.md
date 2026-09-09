# Installation and operation on z/OS

Project owner: **Yarden Lechner**.

## Batch operation: no manual TSO commands

All supplied run paths are JCL jobs. After transferring the source and
customizing the JCL once, submit the appropriate job through your site's
normal submission process or scheduler. No interactive TSO logon or
manual ALLOCATE/FREE sequence is required for an analysis run.

`IKJEFT1B` provides TSO/E inside a batch step. JCL DD statements allocate
the files, `SYSTSIN` invokes R4HAMAX, and the REXX program executes EXECIO
automatically. Seeing TSO commands in source or SYSTSIN does not mean
that an operator must execute them separately.

Use RUN_EXISTING for a prepared dump, RUN_EXTRACT for extraction and
analysis in one job, or RUN_LOGSTREAM for log-stream extraction and
analysis in one job. In the extraction jobs, the analysis step runs only
when extraction returns RC=0. REPORT/CSVOUT and diagnostic output go to
the DD destinations defined in the job, which default to spool.

Source transfer, library provisioning and the first site customization
are installation tasks; the run jobs assume they have been completed.

## Requirements

- TSO/E REXX with EXECIO support for VS/VBS. IBM introduced this support
  in z/OS V2R1. Use the TSO batch environment, not a workstation REXX I/O
  implementation or an assumed equivalent non-TSO host environment.
- IBM RMF Monitor I SMF 70-1 records in the supported layout: Product
  section at least 104 bytes, CPU control section at least 94 bytes,
  and no RMF-level record splitting (`SMF70RAN=0`).
- Read access to an SMF dump, or access to the appropriate SMF log stream
  through the IBM extraction utility.
- Site-specific JOB accounting, classes, UNIT, SPACE and REGION values.

No compilation, link-edit, Python, Regina or third-party package is
required on the mainframe. Regina and Python are development test tools.

## Transfer the source

Use existing source libraries, or allocate text PDS/PDSE libraries such
as `YOURHLQ.REXX` and `YOURHLQ.JCL` with `RECFM=FB,LRECL=80`.
Transfer `src/R4HAMAX.rexx` to member `R4HAMAX` in the REXX library.
The JCL files can use member names EXISTING, EXTRACT, LOGSTRM and SELFTEST.

Transfer **source and JCL as text with ASCII-to-site-EBCDIC conversion**.
Do not add a BOM or sequence numbers. Source/JCL lines fit within 72
columns. In ISPF, inspect quotes, commas, `|`, `\`, `#`, `@`, and `$` after
conversion. Run SELFTEST to catch transfer damage before reading SMF.

**Do not text-convert binary SMF.** SMFIN is a record-oriented data set,
normally VBS output from IFASMFDP/IFASMFDL. A PC file containing raw
BDWs/RDWs is not this input interface. Do not allocate an FB copy and
expect the same parser positions.

## Run SELFTEST

Edit `jcl/SELFTEST.jcl`, point SYSEXEC at your library, and submit it.
SYSTSPRT must contain:

```text
SELFTEST PASS: parser, bounds, flags, dates, filters,
deduplication, Top-N, hourly mean and report.
```

This exercises the parser with in-memory records. It does not exercise
real QSAM/EXECIO reading, SMF record boundaries or production data.

## Analyze an existing dump

Edit `jcl/RUN_EXISTING.jcl`:

| DD/parameter | Set it to |
|---|---|
| SYSEXEC | Your REXX library |
| SMFIN | The binary SMF dump data set |
| DATE | A known day in `YYYYDDD` format |
| SID | One known SID for the first acceptance run |
| DEBUG | Y for the first mapping check, then N |

Start with a small, independently understood dump. Check REPORT,
SYSTSPRT and the RUN step return code. If `CSV=Y`, inspect CSVOUT too.

The sample JCL uses **IKJEFT1B**. IBM documents that it preserves a
nonzero return code from a directly invoked REXX exec and terminates.
This avoids a later SYSTSIN command replacing a failure code, which can
happen under IKJEFT01. See [IBM batch TMP documentation](https://www.ibm.com/docs/en/SSLTBW_3.1.0/pdf/ikjc200_v3r1.pdf).
The samples invoke R4HAMAX directly; avoid wrapping it in a CLIST or
adding unrelated commands whose return codes have different semantics.

REPORT and CSVOUT use `RECFM=VB,LRECL=260`: up to 256 content bytes plus
the RDW. Do not change them to FB 80. EXECIO truncation is an error, not
a successful shortened report.

To retain CSV in a new data set instead of spool:

```jcl
//CSVOUT DD DSN=YOURHLQ.R4HA.CSV,
//          DISP=(NEW,CATLG,DELETE),UNIT=SYSDA,
//          SPACE=(TRK,(5,5),RLSE),
//          DCB=(RECFM=VB,LRECL=260,BLKSIZE=0)
```

Choose a new name or follow local data-set replacement policy. A normal
REXX error return is not necessarily an abend: `DISP=(NEW,CATLG,DELETE)`
does not by itself prevent partial output being cataloged after RC=12.
Downstream processing must check the step RC. Discard partial output
after any RC=12. Download REPORT/CSV as text with EBCDIC conversion.
Import the SID column as text when using a spreadsheet.

## Extract from an SMF archive

`RUN_EXTRACT.jcl` uses IFASMFDP with `TYPE(70(1))` and `OPTIONS(DUMP)`.
It writes a temporary VBS data set, and executes RUN only after
`EXTRACT.RC=0`. Source records are preserved; only temporary output is
deleted when no longer needed. Never substitute CLEAR/ARCHIVE/DELETE
for DUMP merely to produce this report.

The example extraction covers the day before and after the requested
day as well as the day itself. Adjust **both utility dates and REXX DATE**.
This is a practical boundary margin, not a guarantee against arbitrary
write delays. Ensure the source archive actually contains late-written
records and review the utility's SYSPRINT. The REXX filter uses the RMF
measurement timestamp; the utility uses SMF recording timestamps.

## Extract from a log stream

`RUN_LOGSTREAM.jcl` uses IFASMFDL. Replace LSNAME with the real site
stream and retain `OPTIONS(DUMP)`. Do not add SMARTENDPOINT without
reviewing IBM's buffering qualifications: a late-writing image can be
missed by automatic endpoint discovery. The sample does not request
SMARTENDPOINT. See [IFASMFDL parameters](https://www.ibm.com/docs/en/zos/3.2.0?topic=program-specifying-parameters-smf-log-stream-dump).

An empty data set inside a concatenation can cause EXECIO RC=4 and no
data returned. R4HAMAX stops on this I/O error; it does not pretend the
concatenation was completely read. Remove empty inputs from a test
concatenation or prepare a clean consolidated dump using site procedures.

## Acceptance and scheduling

Run the [site acceptance plan](TEST_PLAN.md) before scheduling. Check
expected sample counts and independently verify the largest values.
Do not infer full-day coverage from RC=0. After IPL, observe the warm-up
behavior discussed in [the IBM review](REVIEW.md). Split runs around
source-identity changes and GMT/local offset changes; do not disable
those guards to force mixed input into one result.

For RMF-broken records, this standalone EXECIO path stops with RC=12.
Use an established RMF-aware consumer, or a separately implemented and
validated GRBSMFR-based adapter. GRBSMFR is a callable service, not a
JCL formatter or a drop-in REXX command. This repository does not claim
to supply that adapter.
