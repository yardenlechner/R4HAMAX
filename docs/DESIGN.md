# Design and record interpretation

## Goal and scope

For each selected SID, report the maximum recorded SMF70LAC and Top-N
intervals. Optional hourly statistics summarize the selected LAC
samples. No additional four-hour moving average is calculated.

The output describes the input samples, not an unobserved continuous
peak. Missing intervals can hide a larger value. CPU work on specialty
engines, total CPC utilization, licensing charges and product-specific
sub-capacity are separate measurements; see [the review](REVIEW.md).

## Processing flow

```text
SMF archive or log stream
  -> IBM dump utility (DUMP, TYPE(70(1)))
  -> SMFIN logical records (normally VBS)
  -> EXECIO batches of 256
  -> header / product / CPU / packed-field checks
  -> DATE and SID selection
  -> source identity and local-time-offset consistency
  -> duplicate detection
  -> Top-N per SID, hourly sample statistics, optional CSV
```

REXX is already available under TSO/E and is adequate for a focused
daily batch tool. The dump utilities own extraction; QSAM/EXECIO owns
physical record I/O. The parser does not implement block or log-stream
protocols. There is one production source file and no runtime dependency.

## Offsets and boundaries

The `uint` helper takes a decimal, RDW-relative offset and a byte count.
The REXX string omits the four-byte RDW, while SUBSTR starts at one:

```text
REXX position = RDW-relative offset - 3
LAC position = CPU-control-section offset + 36 - 3
```

Header fields used are RTY at 5, SID at 14, SSI at 18, STY at 22 and
TRN at 24. Product triplet fields are at 28/32/34; CPU control triplet
fields are at 36/40/42. Triplet sizes are 4/2/2 bytes. Bounds are derived
from the actual string length, not a guessed maximum record length.
[IBM header mapping](https://www.ibm.com/docs/en/zos/3.2.0?topic=mapping-headerself-defining-section).

| Relative field | Offset | Bytes | Use |
|---|---:|---:|---|
| Product SMF70PRD | 2 | 8 | Producer check |
| Product SMF70IST | 10 | 4 | Start time |
| Product SMF70DAT | 14 | 4 | Start date |
| Product SMF70INT | 18 | 4 | Duration |
| Product SMF70FLA | 30 | 2 | Collection flags |
| Product SMF70PTN | 50 | 1 | Writing partition number |
| Product SMF70LGO | 60 | 8 | GMT/local offset consistency |
| Product SMF70RAN | 74 | 2 | RMF reassembly indicator |
| Product SMF70XNM/SMF70SNM | 88/96 | 8/8 | Source identity |
| CPU SMF70STF | 5 | 1 | LAC scope and capacity flags |
| CPU SMF70LAC | 36 | 4 | Recorded value |
| CPU SMF70POM/SMF70CSC | 74/78 | 4/16 | CPC identity |

These are section-relative offsets, unlike the header offsets.
[IBM product mapping](https://www.ibm.com/docs/en/zos/3.2.0?topic=mapping-rmf-product-section),
[IBM CPU mapping](https://www.ibm.com/docs/en/zos/3.2.0?topic=s1cpia-cpu-control-section).

The supported input contract requires Product length >=104 and CPU
control length >=94. Larger sections are accepted. Older/converted
shorter layouts are rejected even if they contain LAC: the additional
metadata is needed for the guards. This is an explicit compatibility
boundary, not a claim of support for every historical SMF 70 variant.

## Structural checks

The parser checks lengths before reading, header format/subtype bits,
subtype 1, at least two triplets and the declared triplet-table extent.
Both consumed sections must be singleton, start beyond the table, fit
inside the record, and not overlap each other. Unused data sections are
not fully validated; this is not a general SMF integrity validator.

Both SSI and product name must identify RMF. Monitor III records are
excluded with a counter, so independent collection streams are not
mixed. Compatible-looking records from CMF or another producer require
a separate mapping validation; they are not silently accepted.

Any nonzero RAN stops processing, before CPU-section interpretation.
This prevents an RMF fragment from being confused with a complete
interval. Zero means the record is not RMF-broken. Unknown nonzero
values also fail closed. This guard is applied before selection filters.

## Packed values and arithmetic

Date, start time and duration use `0cyydddF`, `0hhmmssF` and `mmsstttF`.
The year is `1900+cyy`. The decoder validates decimal nibbles, positive
sign (documented F, plus accepted positive C), Julian day, time ranges
and a nonzero duration. Negative D and invalid digits are rejected.

Binary fields are big-endian unsigned values read with X2D(C2X(...)).
NUMERIC DIGITS 20 retains the precision needed for all arithmetic used
here. An unsigned boundary test verifies decoding; a syntactically valid
enormous value is not a claim that it is plausible hardware usage.

End time is computed in integer milliseconds. This duration format is
less than 100 minutes, so at most one midnight is crossed. Gregorian
leap-year rules apply, including century exceptions. Both dates must
remain in the supported 1900-2899 range.

## Day and hour assignment

END is the default sample timestamp; START is available for comparison
with tools that label intervals by their start. DATE selection and hour
grouping both follow DAYMODE. A 09:45-10:00 interval is assigned to
hour 10 in END mode. An end at midnight belongs to the new day.

This is a sample-label convention. It does not allocate CPU consumption
across hour boundaries. Projected interval end is not substituted for
the recorded start-plus-duration measurement. No UTC conversion is done.

Selected samples for a SID must have one consistent raw LGO value.
A change, including DST, stops the run. This avoids merging repeated
local hours. Split and interpret such runs explicitly. Clock anomalies
with unchanged LGO are not all detectable; input-time validation remains
part of acceptance.

## Identity and duplicates

The identity guard compares raw CPC plant/sequence, writing partition
number, sysplex name and system name. If these change under one SID,
the run stops. A legitimate move or rename also requires separate runs.
Unavailable blank/null identity metadata produces a warning, not an
assertion that the source was verified. The caller must still ensure
SID uniqueness. Identity is not used to construct a CPC sum.

After identity checks, the duplicate key is `(SID,start,end)` and the
value signature is `(LAC,STF-bit3)`. Matching samples are counted once;
conflicts stop the run. This compares measurement identity, not every
byte of each record. Raw diagnostic flag variants can be duplicates.

Up to 250,000 unique selected keys are retained. Reading in batches
limits retained record bodies but does not make memory constant: keys,
Top-N and hour summaries remain. The cap is an operational ceiling, not
a guarantee that 64 MB holds that many keys. Split larger runs by day.
SID/hour enumeration uses indexed stems rather than repeatedly scanning
ever-growing word lists. Top-N uses at most 100 comparisons/shifts per
sample. Ties preserve input order; groups retain first-discovery order.

## Hourly statistics

Each `(SID,sample-date,sample-hour)` has N, sum, maximum, duration minimum,
duration maximum and STF-off count. MEAN_MSU is `sum/N`, unweighted.
PEAK_HOURLY_MEAN is selected before rounding; display uses three decimals.

For equal intervals, this is a useful descriptive hourly statistic.
For unequal intervals it remains a mean of samples, not a time-weighted
utilization measure. No gap filling, overlap removal, cross-hour splitting
or completeness proof is provided. N and MIN_MS/MAX_MS are diagnostics,
not coverage percentages. SCRT uses additional rules and can attribute
hours differently; this mode is not a billing engine.

## Flags, diagnostics and output

The scope flag is retained with every result. A peak with STF bit 3 off
is specifically marked. Raw input counts also flag skipped RMF samples,
record-level conversion, boost and capacity/service-unit changes; see
[REVIEW.md](REVIEW.md) for their interpretation and source references.

Raw input flag counters occur after structural/producer checks but
before DATE/SID filtering, and include duplicates. Weak-identity checks
occur after selection and also include duplicates. STF_OFF counts unique
selected samples. Rejection counters may refer to unselected input.

CSVOUT contains SID, sample/start/end, milliseconds, LAC and scope bit.
It is emitted in input order after deduplication. REPORT is streamed
after input completes. A write/truncation/close error returns RC=12.
SYSTSPRT gets the error and, for a write failure, the attempted line.
There is no fallback full report; discard partial output and rerun.

DEBUG stores the first 70-1 triplet map and up to 48 header bytes. It also
retains WLA/LAC HEX and decimal, STF, section location and timestamp for
at most three unique selected samples in input order, across all SIDs.
These are not necessarily peak samples. It is not a dump of every record. No credentials or live SMF data are included
in this repository or required by its desktop tests.
