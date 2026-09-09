# FIXES LOG

Project owner: **Yarden Lechner**

Review date: **2026-09-09**

This log records what to correct, why it matters, what the GitHub version
already implements, and what must still be checked on z/OS.

## Scope and publication rules

This checklist documents the maintained R4HAMAX implementation only.
Do not publish private source photographs, private program names, site
identifiers, dataset names, or production values. Use invented examples
for tests and explanations. The owner's public credit above is intentional.

Transfer the current source to the intended SYSEXEC library before testing
a new revision. Repository changes do not automatically update site members.

## WLA versus LAC: synthetic examples

These numbers are invented for regression testing, not production evidence:

| Example | WLA bytes | WLA | LAC bytes | LAC / R4HA |
|---|---|---:|---|---:|
| A | `00000049` | 73 | `0000000C` | 12 |
| B | `0000003A` | 58 | `00000009` | 9 |

WLA is processor capacity available to the image; LAC is the recorded
long-term average. The field offsets within CPU Control are 32 and 36,
respectively, each four bytes. In a REXX string containing just that
section, their positions are 33 and 37:

```rexx
wla = C2D(Substr(ctlSection, 33, 4))
lac = C2D(Substr(ctlSection, 37, 4))
```

[IBM CPU Control mapping](https://www.ibm.com/docs/en/zos/3.2.0?topic=s1cpia-cpu-control-section).

Reading or labeling WLA as R4HA reports capacity instead of the recorded
rolling average. Verify both field offsets and output labels. The repository's
LAC extraction uses offset 36 without shifting or scaling.

**Do not divide LAC by four.** A 15-minute recording cadence does not
change the units of an already computed four-hour rolling average.
The regression checks that the invented records return LAC 12 and 9,
never the adjacent WLA 73 and 58.

## Correction and verification checklist

| Check | Why it matters | Current R4HAMAX status | Host verification still needed |
|---|---|---|---|
| DATE filter actually applied | Displaying a date argument is not sufficient; selection must use it | Implemented in `process`, using the chosen START/END sample date | Use a known multi-day dump; verify included dates and DATE_FILTER count |
| Measurement timestamps | Common SMF header time can differ from the measurement interval | Uses Product DAT/IST/INT; calculates END with midnight rollover | Compare the same SID and actual interval; check late-written records |
| Read/write/close failures | A later success must not overwrite an earlier I/O failure | Read, write, truncation and close failures terminate with RC=12 | Test actual step/scheduler RC and discard partial output |
| Section and producer checks | Bounds alone do not prove the expected mapping or semantics | Validates consumed triplets, overlap, producer and Monitor I; stops on nonzero RAN | Confirm site layout; distinguish VBS spanning from RMF splitting |
| STF bit 3 | LAC semantics depend on the scope flag | Retained per sample; warnings and RC=4 when off | Inspect raw STF and explain any off values |
| All-zero day | A zero-initialized maximum can leave the first zero sample without a timestamp | First zero sample is retained in Top-N with its timestamp | Check an all-zero test input produces a dated zero peak |
| Rejected-record visibility | Silent arbitrary value ceilings can hide records and invalidate a peak | Named rejection counters; no arbitrary LAC/WLA ceiling | Reconcile counts; a valid binary number is not proof of physical plausibility |
| Storage usage | Retaining every output row unnecessarily increases storage demand | Input batches of 256; streamed CSV/report; retained duplicate keys capped at 250000 | Measure REGION/CPU for the real daily volume |
| Preserve earlier output | Pre-deleting an earlier result loses it even if a new run fails | Supplied run jobs use spool and do not pre-delete a named prior report | If saving datasets, use distinct run names or a site GDG policy; accept only after RC checks |
| Raw field diagnostics | Earlier R4HAMAX DEBUG showed header/triplets but not LAC bytes | Added bounded selected-sample WLA/LAC HEX+decimal and STF diagnostics | Match the debug values against an independent formatter |

## DEBUG added in this update

Use `DEBUG=Y` in the existing job's SYSTSIN invocation. The report retains
its first Type 70-1 header/triplet diagnostic and additionally shows at most
three **unique selected** samples, in input order:

- SID and sample timestamp;
- CCS offset, CPU section length, and LAC position in the RDW-free string;
- WLA HEX and decimal;
- LAC HEX and decimal;
- STF HEX and bit 3.

These are not necessarily the daily peak samples, and the limit is across
all selected SIDs. Use a single SID and a focused input extract when
investigating a particular interval. Duplicates and filtered samples do
not consume the three-sample limit. DEBUG=N produces no extra field trace.
The trace does not alter peak selection, CSV columns or hourly arithmetic.

## What remains an operating check, not an implemented feature

- Verify the actual source member and library executed by the job.
- Verify extraction contents; a date in a dataset name is not a filter.
- Verify complete coverage and compare like-for-like metrics in another tool.
- Resolve missing/overlapping intervals and legitimate source/time-zone changes
  before combining data. There is no automatic gap repair or UTC timeline.
- Review IPL warm-up, Boost, conversion and capacity-change flags.
- Use a validated RMF-aware solution for broken records; reassembly is not
  implemented here. R4HAMAX stops rather than accepting fragments.
- Distinguish interval peak, hourly sample mean and SCRT licensing output.
- A normal nonzero return can still leave a cataloged partial dataset;
  DISP alone is not a substitute for checking the job's result.

## Validation evidence and acceptance

The automated suite exercises the actual REXX parser with synthetic data,
including distinct adjacent WLA/LAC values, the three-sample debug limit,
filtered/duplicate exclusion, report emission and DEBUG=N behavior.
Existing tests cover dates, zero peaks, bounds, flags and simulated I/O
failures. A successful desktop/CI run does not establish host acceptance.

Complete host acceptance is still required. Record actual transfer, VBS,
date/peak, I/O and scheduler results using [the acceptance plan](docs/TEST_PLAN.md).
Keep site evidence outside the public repository. See [DESIGN](docs/DESIGN.md)
for behavior and [REVIEW](docs/REVIEW.md) for additional IBM findings.
