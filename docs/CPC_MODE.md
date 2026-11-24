# Running the raw hourly CPC diagnostic

`CPC=Y` adds concurrent LPAR aggregation to R4HAMAX. It reports raw
recorded LAC hourly means and sums. It does not implement SCRT capacity
adjustments, N5 integer rounding, product activity or billing rules.
See [the evidence ledger](SCRT_RULES.md) for what is known and pending.
Desktop tests construct binary records in code. The five-value teaching
sequence in the evidence ledger is independently invented. Example names
and fixture population counts illustrate test cases; they are not a verified
production inventory. Customize the input inventory locally and keep actual
site names and comparison traces outside this public repo.

## Supported input for this increment

- Native z/OS LPARs, each supplying its own RMF Monitor I SMF70-1 stream.
- Exactly 15-minute intervals starting at :00, :15, :30 or :45, with
  zero seconds and milliseconds in the start label.
- One stable raw `SMF70LGO` offset for all selected LPARs on a CPC.
- Zero `SMF70HOF` hypervisor date/time offset. Known simplified z/VM
  guest data is rejected; site verification must establish native LPARs.
- An explicit inventory that stays fixed throughout the selected day.
- The shared parser's existing complete-record, producer and layout
  requirements. LAC scope bit 3 must be on; it is not a generic validity
  certificate or a sufficient test for native versus virtualized LPARs.

This is a conservative implementation profile. SCRT can accept other
configurations. Do not change your RMF collection settings just to fit
this profile; report the difference so support can be extended with
evidence and tests. An unsupported observation fails with RC12, while a
missing expected interval makes its hour incomplete.

## 1. Declare the physical LPAR inventory

Create `YOURHLQ.R4HA.CPCMAP` as a text data set, for example FB 80. Each
noncomment line contains exactly two whitespace-separated fields:

```text
CPC_HEX PTN
```

The line above describes the format, not a header to put in the data
set. `CPC_HEX` is exactly 40 hexadecimal characters representing the
original 20 bytes `SMF70POM || SMF70CSC`. `PTN` is the decimal writing
partition number (`SMF70PTN`, 0..255). Blank lines and lines beginning
with `#` are ignored. Duplicate inventory members are errors.

For example, on a site whose character conversion uses IBM-037, the
synthetic plant `TEST` and sequence `0000000000000001` are represented by:

```text
# Synthetic only: two expected partitions on one test CPC
E3C5E2E3F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F1 1
E3C5E2E3F0F0F0F0F0F0F0F0F0F0F0F0F0F0F0F1 2
```

Replace these with **the raw bytes from your actual records** using a
trusted SMF formatter. Do not hex-encode an ASCII-translated machine
name: desktop synthetic fixture bytes and mainframe EBCDIC bytes differ.
Plant and sequence must each be nonblank. Confirm the inventory against
site configuration; a record-only discovery cannot find a missing LPAR.

List every expected z/OS LPAR on each CPC being analyzed, regardless of
sysplex. The inventory is scoped to this z/OS calculation; it does not
assert that z/VM, Linux or inactive hardware partitions are measured.
An undeclared physical partition in selected data is a configuration
error. A declared partition with no records remains visible as missing.

The first increment expects the same population for all 24 local hours.
Scheduled shutdowns, IPL gaps and moves can therefore yield incomplete
hours. Do not remove a member from the inventory merely to make the
status complete. Time-bounded membership is follow-up work.

## 2. Prepare and submit the job

Transfer the source as described in [INSTALL.md](INSTALL.md), keeping
binary SMF binary. Customize [RUN_CPC.jcl](../jcl/RUN_CPC.jcl):

| Setting | Meaning |
|---|---|
| `SYSEXEC` | Library containing the updated R4HAMAX member |
| `SMFIN` | All relevant SMF dumps; concatenate additional inputs as needed |
| `CPCMAP` | Verified expected CPC/partition population |
| `DATE=YYYYDDD` | One local reporting day; mandatory in CPC mode |
| `SID=*` | All physical writers; subset SID filters are rejected |
| `HOURLY=Y` | Required for CPC hourly aggregation |
| `CSV=Y` | Optional per-record audit output |

```jcl
 %R4HAMAX CPC=Y DATE=2026251 SID=* HOURLY=Y CSV=Y
```

No interactive TSO session, Python, compilation or link-edit is needed
on the mainframe. This JCL reads existing dumps without changing them.
It shows one placeholder input. Add unnamed DD statements under `SMFIN`
for additional files; no fixed file count or sysplex arrangement is implied.
Use the site's existing extraction procedure and verify completeness,
including late-written SMF. Remove empty concatenation members rather
than ignoring EXECIO read errors.

`DAYMODE` and `TOP` keep their legacy parameter validation, but do not
select the CPC reporting grid or the number of CPC peak rows. CPC mode
uses midpoint attribution and prints all 24 hours plus one observed
peak. `DEBUG` remains the legacy SID trace option; use the CPC CSV for
record-level audit in this mode.

## 3. Interpret the report

The report starts with `RAW LAC ONLY - NOT SCRT / N5 / BILLING`.
Each CPC block identifies the exact inventory key and LGO value.

| Output | Interpretation |
|---|---|
| `LPAR_HOUR ... STATUS=COMPLETE RAW_MEAN_MSU=...` | Four distinct accepted quarter-hour samples for that physical partition |
| `CPC_HOUR ... STATUS=COMPLETE RAW_MSU=...` | Sum of complete LPAR hourly means for the declared CPC population |
| `STATUS=INCOMPLETE` | An expected slot/partition is absent; there is no numeric CPC total for that hour |
| `COMPLETE_HOURS` / `INCOMPLETE_HOURS` | Completeness of the selected day against the declared inventory |
| `OBSERVED_COMPLETE_HOUR_PEAK` | Greatest concurrent raw sum among complete observed hours |
| `FULL_DAY_PEAK_NOT_PROVEN` | Incomplete hours prevent treating the observed peak as a verified day peak |
| `NO_COMPLETE_HOUR_PEAK` | No hour contains every expected contribution |

A complete zero-valued hour has numeric zero. A missing hour has no
numeric total. The four-slot count is sufficient **only because** the
parser requires the exact fixed-duration grid and deduplicates each
physical partition/hour/slot. A count of four arbitrary intervals is
not a general coverage test.

Values retain precision through aggregation; the report displays three
decimals. Peak selection is performed before formatting. Ties select
the earliest hour. There is no sum of independent LPAR maxima.

The raw identity key is CPC plus PTN. Same SID on another CPC is a
separate writer. Repeated physical measurements under a different SID
label cannot inflate a total when their remaining source identity and
values agree. Changed identity or conflicting values stop the run.
Inventory/report order follows CPCMAP, not SMF arrival order.

## 4. Audit output and return codes

CPC mode has its own CSV header. It includes raw CPC/PTN and SID,
start/end, assigned hour, duration, LAC, WLA, LGO, HOF and scope/flags.
WLA is an audit field in this increment, not a cap applied to LAC.
CSV emits accepted unique records in input order. Diagnostic flag
variants may count as duplicates; global flag counters still include
their indications. Do not feed this schema into a legacy SID CSV parser.

- **RC0:** selected data passed the supported profile and every expected
  CPC/hour had all four slots for every inventory member, with no counted
  warnings. This does not validate the supplied inventory or prove SCRT
  compatibility, SMF producer correctness, or an unobserved peak.
- **RC4:** missing hours/slots, duplicate copies or existing parser/input
  warnings. Read the report; incomplete periods have limited conclusions.
- **RC12:** unsupported profile, inventory error, conflicting physical
  measurements, identity/offset changes, RMF splitting or I/O failure.
  Discard all partial REPORT/CSVOUT, even if a data set was cataloged.

Source flag counters can include unselected dates and duplicate records,
as in legacy mode. Records with ordinary malformed shared-parser fields
are rejected with warning counts; they cannot create missing slot values.

## 5. Acceptance and the next compatibility stage

Run both desktop suites and then the host checks in
[TEST_PLAN.md](TEST_PLAN.md). Validate at least one complete and one
deliberately incomplete disposable input. Independently check physical
identity, interval boundaries, LGO/HOF, contributor means and CPC sums.

For SCRT reconciliation, start with the precise report section, version,
same input period and actual per-record capacity data, retained privately.
The fictional five-value teaching example produces raw 52.5 for end-labeled
intervals and 50 for start-labeled intervals. Its hypothetical target of
45 is not an observed SCRT result. Follow
[SCRT_WORKFLOW.md](SCRT_WORKFLOW.md) to establish the rules before adding
capacity/rounding compatibility logic.
