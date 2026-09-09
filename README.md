# R4HAMAX — recorded R4HA peaks from z/OS SMF

**Author and project owner: Yarden Lechner**

TSO/E REXX that reads **SMF Type 70 Subtype 1**, extracts `SMF70LAC`,
and reports the peak and Top-N **per SID**. Optional CSV output and hourly
sample means are included. No compile or link is required on z/OS.

**Validation status:** synthetic parser and regression tests run under
Regina REXX locally and in GitHub Actions. Real SMF, TSO/E EXECIO, EBCDIC
transfer and JCL require the [site acceptance tests](docs/TEST_PLAN.md).
See the [IBM-based review](docs/REVIEW.md) for findings and limitations.

## What this measures

`SMF70LAC` already contains the recorded long-term / four-hour rolling
average. The program finds its largest recorded value; it does not average
another four hours of LAC values. A peak between RMF records may be missed.

| Output | Definition |
|---|---|
| Rank 1 for each SID | Maximum selected interval SMF70LAC |
| Hourly `MEAN_MSU` | Arithmetic mean of unique samples assigned to that hour |
| Hourly `MAX_MSU` | Largest sample assigned to that hour |
| `PEAK_HOURLY_MEAN` | Highest hourly sample mean for each SID |

For samples of 100, 160 and 130 MSU in one hour, the interval peak is 160
and the sample mean is 130. **Hourly output is not an SCRT calculation.**
It does not apply licensing rules, duration weights, gap filling or
interval splitting across hours. SIDs are never summed into a CPC peak.

## Files

| File | Purpose |
|---|---|
| [FIXES LOG.md](FIXES%20LOG.md) | Possible corrections: what to check, what to change, and why |
| [src/R4HAMAX.rexx](src/R4HAMAX.rexx) | Complete program and built-in SELFTEST |
| [jcl/RUN_EXISTING.jcl](jcl/RUN_EXISTING.jcl) | Read an existing SMF dump |
| [jcl/RUN_EXTRACT.jcl](jcl/RUN_EXTRACT.jcl) | IFASMFDP followed by REXX |
| [jcl/RUN_LOGSTREAM.jcl](jcl/RUN_LOGSTREAM.jcl) | IFASMFDL followed by REXX |
| [jcl/SELFTEST.jcl](jcl/SELFTEST.jcl) | Synthetic tests under TSO/E |
| [docs/INSTALL.md](docs/INSTALL.md) | Installation and operating instructions |
| [docs/DESIGN.md](docs/DESIGN.md) | Mapping, algorithm and defensive checks |
| [docs/REVIEW.md](docs/REVIEW.md) | IBM findings, fixes and remaining boundaries |
| [docs/TEST_PLAN.md](docs/TEST_PLAN.md) | Automated tests and host acceptance |
| [docs/SOURCES.md](docs/SOURCES.md) | Primary IBM references |
| [examples/report.txt](examples/report.txt) | Actual output from synthetic inputs |
| [tests/run_checks.py](tests/run_checks.py) | Local and CI regression runner |

## Quick installation

1. Transfer `src/R4HAMAX.rexx` as **text**, converting to the site's EBCDIC
   code page, into member `R4HAMAX` of `YOURHLQ.REXX`. An FB 80 PDS/PDSE
   is suitable; source lines are at most 72 characters.
2. Transfer the JCL as text. Replace the JOB card, classes, `YOURHLQ`,
   dataset names and log stream placeholders for your site.
3. Submit `SELFTEST.jcl`; require `SELFTEST PASS` and successful completion.
4. Run `RUN_EXISTING.jcl` against a small, known dump with DATE and SID set.
5. Inspect REPORT, CSVOUT, SYSTSPRT and the RUN step return code.

**Keep SMF binary.** Do not text-convert SMF or turn it into FB records.
Input is a dataset of logical SMF records, normally VBS from an IBM dump
utility. A workstation file containing raw BDWs/RDWs is not this interface.

## Run everything through jobs

After the one-time source transfer and site-specific JCL setup, submit
one of these jobs. No interactive TSO session or manual ALLOCATE/FREE
commands are required to run the analysis.

| Input | Submit | Processing in the job |
|---|---|---|
| Existing dump | `jcl/RUN_EXISTING.jcl` | REXX analysis and reports |
| SMF archive | `jcl/RUN_EXTRACT.jcl` | IFASMFDP extraction, then REXX analysis and reports |
| SMF log stream | `jcl/RUN_LOGSTREAM.jcl` | IFASMFDL extraction, then REXX analysis and reports |
| Installation check | `jcl/SELFTEST.jcl` | REXX synthetic self-test |

`IKJEFT1B` starts the TSO/E environment **inside the batch job**. The DD
statements allocate input, source library and outputs. `SYSTSIN` supplies
the REXX invocation automatically, for example:

```jcl
//SYSTSIN  DD *
 %R4HAMAX DATE=2026251 SID=SYSA TOP=10 DAYMODE=END +
   HOURLY=Y CSV=Y DEBUG=N
/*
```

These lines belong in the supplied JCL; they are not an extra command
to type at a terminal. The program's `ADDRESS TSO 'EXECIO ...'` statements
also run automatically in that batch environment. TSO/E is the runtime,
not a requirement for interactive operation. Submit through your site's
normal JES submission or scheduler process and retrieve the spool output.

`IKJEFT1B` propagates a directly invoked REXX failure. Validate scheduler
handling at your site; see installation notes.

## Parameters

| Parameter | Default | Values |
|---|---|---|
| `DATE` | `*` | `YYYYDDD`, years 1900–2899, or all dates |
| `SID` | `*` | 1–4 of A–Z, 0–9, `#`, `@`, `$`, `.`; or all SIDs |
| `TOP` | `10` | 1–100, per SID |
| `DAYMODE` | `END` | Assign sample to interval `END` or `START` |
| `HOURLY` | `Y` | Produce hourly sample means: Y/N |
| `CSV` | `N` | Write accepted unique samples to CSVOUT: Y/N |
| `DEBUG` | `N` | First mapping plus up to 3 selected WLA/LAC/STF traces: Y/N |

`SELFTEST` is a separate mode, without other parameters or SMFIN.
Repeated parameters use the last value. Arguments are uppercased.

## Input and time contract

- Supported input is unbroken IBM RMF Monitor I Type 70-1 data with a
  product section of at least 104 bytes and CPU control of at least 94.
  Unknown or shorter layouts require review, not guessed offsets.
- Nonzero `SMF70RAN` stops the run: RMF application-level fragments must be
  reassembled first. EXECIO's VBS support alone does not do that.
- `END = START + DURATION`, including milliseconds, midnight and leap years.
  Under END mode, midnight belongs to the new day. `2026251` is 2026-09-08.
- Time is RMF local time. A selected SID's source identity or GMT/local
  offset changing stops the run. Split migrations or clock changes into
  separate runs; there is no UTC normalization.
- Equal SID/start/end samples with equal LAC and STF scope are counted
  once. Conflicting duplicates stop the run. Top-N ties retain input order;
  SIDs and hours appear in discovery order.
- LAC describes the writing image. One image's record does not provide the
  LAC values of every partition listed elsewhere in that record.

## Return codes

| REXX RC | Meaning |
|---|---|
| 0 | Samples found, with none of the counted warning conditions |
| 4 | No samples, rejected records, duplicates, scope/skipped-sample warnings, Boost/conversion/capacity-change flags, or weak identity metadata |
| 12 | Invalid parameters, I/O failure, conflicting duplicates, split RMF records, identity/time-zone changes, sample limit or REXX condition |

Some input flag counts precede DATE/SID filtering; see the design document.
RC 0 does not prove complete coverage. Discard partial REPORT/CSVOUT after
RC 12. Errors appear in SYSTSPRT.

## Development checks

Regina REXX and Python are needed for workstation tests only:

```text
regina src/R4HAMAX.rexx SELFTEST
python tests/run_checks.py regina
```

On Windows, the second argument can be the full path to `regina.exe`.
Tests use synthetic data and write temporary files under ignored `.work/`.
GitHub Actions runs the same checks on Linux. No real SMF is uploaded.

## Operating limits

Input is read in batches of 256. Duplicate keys are retained for up to
250,000 unique samples, alongside per-SID Top-N and hourly aggregates.
This ceiling does not guarantee a fit in REGION=64M; measure host storage
and split large input by day.

Review IPL warm-up, gaps, overlapping intervals and extraction completeness.
WLM initializes its history with zeros at IPL; the program preserves recorded
LAC rather than inventing a correction. Boost flags are reported without
rescaling LAC. Full RMF reassembly, gap detection and SCRT reproduction are
outside this implementation. The [review](docs/REVIEW.md) explains why.

This repository is public. Examples use synthetic records and placeholders.
Do not commit real SMF, credentials or sensitive site identifiers.
