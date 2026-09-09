# Tests and site acceptance

## Automated checks

Run the production source's in-memory checks with:

```text
regina src/R4HAMAX.rexx SELFTEST
python tests/run_checks.py regina
```

On Windows, pass a full path to regina.exe if necessary. Python uses only
its standard library. The suite executes the real REXX parser, calendar,
selection, ranking and reporting routines. A Python-built record uses
independent field offsets based on IBM's published example boundaries
(9 triplets, Product 100/104, CPU control 204/344), avoiding reliance on
the REXX fixture builder alone.

Desktop text fields are ASCII to match the desktop interpreter. This
does **not** test EBCDIC conversion or an actual mainframe binary dump.
All generated files are stored in ignored `.work/`.

| Area | Checks |
|---|---|
| Parameters | Invalid dates, options and TOP bounds; national SID characters |
| Mapping | Independently built sections at different offsets; format/producer guards |
| Bounds | Every truncated prefix of a fixture; short sections; bad triplets; overlap |
| Calendar | Python Gregorian oracle, century rules, milliseconds and midnight |
| Values | Zero, unsigned 32-bit conversion, stable ties, per-SID ranking |
| Selection | START/END, DATE, SID, multiple systems/dates |
| Duplicates | Equal samples ignored, conflicting samples fatal |
| Provenance | Changed machine/name or LGO fatal; missing identity warning |
| RMF | Broken/unknown RAN fatal, Monitor III excluded, metadata warnings |
| Hourly | Independent SID grouping, sample count/mean/max and peak mean |
| I/O simulation | Two batches, EOF with records, CSV contents and closes |
| Failures | Read error, empty concatenation RC=4, truncation RC=1, close/write errors |
| Limits | Unique-sample ceiling and zero-result behavior |
| Delivery | Real generated report, ASCII source, 72-column REXX/JCL |

Only ADDRESS TSO calls are replaced in temporary I/O test drivers.
The suite also checks the real top-level success/warning return path.
Regina Windows can normalize nonzero process exit codes; that is not
evidence of the JCL return code. TSO/E return behavior must be checked
on the host. GitHub Actions runs the suite on Linux as a second host.

## z/OS acceptance -- required before operational use

No real mainframe connection or production SMF was used during this
review. The following tests remain site responsibilities.

1. **Transfer:** run SELFTEST.jcl under IKJEFT1B. Inspect punctuation,
   code-page conversion, line lengths and SYSTSPRT.
2. **Actual VBS:** read a known dump, including a record physically
   spanned by QSAM. Check that the EXECIO string excludes RDW and that
   DEBUG triplets locate the expected sections. Distinguish this from
   RMF-level splitting (RAN), which must stop this program.
3. **Mapping:** compare at least five LAC/start/end/duration values to
   a trusted formatter or capacity tool on the same release. Confirm
   Product/CPU minimum lengths and identity metadata are appropriate.
4. **Peak:** compare the complete selected day's maximum and Top-N;
   align START/END conventions before drawing conclusions.
5. **Boundaries:** test midnight, leap day/year rollover and late-written
   SMF. Ensure the extraction margin actually includes needed records.
6. **Completeness:** compare N and input counts with source inventory.
   Remove one interval from a disposable copy and verify the count falls.
   RC=0 and a plausible peak must not be interpreted as complete coverage.
7. **Unequal/overlapping intervals:** observe MIN_MS/MAX_MS and compare
   sample means manually. The program does not time-weight or resolve
   overlapping intervals. Use a clean Monitor I stream for final results.
8. **Scope:** check STF-off, converted records, boost and capacity-change
   counters. Check a known IPL/restart period against WLM expectations.
   Four hours of pre-IPL CPU use are not reconstructed by this program.
9. **Identity/time:** test two SIDs, a SID reused for another source,
   a legitimate partition move, and an LGO change. Changes must fail
   rather than silently mix. Check unknown identity metadata manually.
10. **Duplicate copies:** matching samples must not raise N; change LAC
    in one disposable copy and verify RC=12 and rejection of partial CSV.
11. **JCL/I/O:** test missing SMFIN, short output LRECL, unavailable CSVOUT,
    an empty concatenation member and no matching date. Verify the actual
    step/scheduler RC and downstream output disposition. Do not modify
    production source data to perform these tests.
12. **Extraction:** submit the relevant utility JCL; verify SYSPRINT,
    source preservation and that RUN is skipped if EXTRACT is not RC=0.
13. **Volume:** measure CPU/storage on a representative day. REGION=64M
    is a starting point; history retention may require more or smaller runs.

Record z/OS/RMF versions, applicable maintenance, parameters, counts,
comparison evidence and step RC. Store sanitized evidence; do not upload
real SMF records or sensitive site identifiers to the public repository.

## Acceptance decision

Accept only after TSO/E SELFTEST, real VBS/JCL and independent field/peak
comparisons pass and all warnings are explained. The review can identify
known risks and add guards; it cannot certify the absence of all future
bugs or data-gatherer defects. A SCRT mismatch alone is not a parser bug
because its metric and aggregation policy may differ.
