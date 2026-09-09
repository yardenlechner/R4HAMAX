# IBM literature and code review

Review date: 2026-09-09. Scope: the standalone R4HAMAX reader, JCL,
tests and documentation. This is a code/mapping review, not IBM
certification or a completed z/OS acceptance test.

## Findings addressed

| Finding | Change and regression evidence |
|---|---|
| SID validation was too restrictive | Allow A-Z, digits, national characters and period; a `#@$.` SID passes through the actual parser |
| RMF-level splitting was not recognized | Check RAN and stop on nonzero before consuming CPU data; tests cover broken and unknown indicators |
| Header/producer assumptions were implicit | Require subtype-format bits and RMF names; reject Monitor III to keep one collection source |
| One SID could combine different sources | Compare CPC/partition/sysplex/system metadata before deduplication; changed identity is fatal |
| Repeated local hours could be merged | Require stable LGO per selected SID; an offset-change test must fail |
| Important measurement flags were invisible | Count boost, conversion and capacity-change indications, retaining recorded LAC with warning RC |
| SID/hour lists scaled poorly | Replace repeated word-list appends/scans with indexed stems |
| Later batch commands could obscure errors | JCL now uses IKJEFT1B; real host RC tests remain in the acceptance plan |
| Tests shared most fixture assumptions | Add a separately constructed IBM-layout record, truncation sweep and negative I/O paths |
| CI used a deprecated action runtime | Update checkout to the current documented v7 action |

## 1. A SID is not limited to letters and digits

IBM's SMFPRMxx SID definition includes national characters and periods.
The old validation could reject legitimate systems. The new shared
validator is used for both the command parameter and record contents.
Keys still use hex-encoded SID bytes, so punctuation does not alter stem
indexing. [IBM SMFPRMxx SID definition](https://www.ibm.com/docs/en/zos/3.1.0?topic=ssmfsp-statements-parameters-smfprmxx).

## 2. VBS spanning and RMF splitting are different layers

EXECIO supports VS/VBS logical records; it does not make this program an
RMF reassembly engine. IBM supplies GRBSMFR for retrieving and optionally
reassembling data-gatherer-broken records. The program explicitly stops
for RAN != 0 rather than reporting a potentially partial result.
[IBM GRBSMFR service](https://www.ibm.com/docs/en/zos/3.1.0?topic=sr-obtaining-smf-record-data-from-data-set-log-stream-grbsmfr).

This is a supported-input restriction. It does not mean split records
are corrupt. A GRBSMFR-based solution needs a separately validated
adapter and calling environment; none is silently simulated here.

## 3. LAC belongs to the writing image

Reading one image's Type 70 data is not enough to obtain every LPAR's
LAC just because other partition sections are present in the record.
IBM's capacity table describes this value as available from the writing
partition. The report therefore keeps individual SID results and does
not sum partition-section values or individual peaks.
[IBM CP_CPU_LPAR_H definition](https://www.ibm.com/docs/en/zp-and-ca/3.1.0?topic=tables-cp-cpu-lpar-h).

Raw identity checks catch many SID collisions and changes, but missing
metadata or a carefully indistinguishable source remains possible.
Input provenance is still part of the operating contract.

## 4. IPL changes the interpretation of early values

IBM explains that WLM begins with a four-hour interval containing no
partition CPU usage at IPL. Early recorded R4HA values therefore do not
represent four hours of actual post-IPL load. R4HAMAX reports the field
as recorded; it neither replaces zero nor reconstructs pre-IPL history.
The report reminds users to inspect IPL warm-up and gaps. Automatic
exclusion of the first four hours is not implemented.
[IBM WLM and Workload License Charges](https://www.ibm.com/docs/SSLTBW_3.2.0/com.ibm.zos.v3r2.ieaw100/lcharg.htm).

## 5. Boost and capacity are not reasons to invent a new LAC

IBM documents that the long-term average during boost is based on
general-purpose consumption at the standard processor rating. Boost
does not directly increase the reported R4HA in the same way that total
observed throughput can increase. The program records warning counters
but does not apply a guessed boost multiplier.
[IBM WLM changes during boost](https://www.ibm.com/docs/en/zos/3.1.0?topic=considerations-wlm-changes).

STF bits 1/2 signal capacity/service-unit changes; bit 3 determines LAC
scope. FLA reports skipped samples, Monitor III origin, conversion and
boost. The implementation's policy is conservative: Monitor III is
excluded; the other named indications retain LAC and produce warnings.
Some warn about context rather than invalid data. No inference that all
other fields in the record are valid is made from these flags.

## 6. Dates and hourly means are definitions, not universal labels

The tool uses recorded start plus duration for END and buckets samples
by the chosen label. A projected gathering-end token is not substituted
for an actual interval boundary. Local clock/DST changes need separate
runs. Duration variation and missing observations can bias an arithmetic
sample mean. It remains labeled as such; no coverage or SCRT equivalence
is asserted. See [the design](DESIGN.md) for the exact arithmetic.

## 7. Extraction and output can fail without an obvious parser bug

EXECIO can return RC=1 for output truncation, RC=2 for EOF before the
requested count, RC=4 for an empty concatenation member, and RC=20 for
severe failure. The reader consumes the final RC=2 batch; the other
nonzero I/O outcomes stop the run. Close results are checked too.
[IBM EXECIO](https://www.ibm.com/docs/en/zos/3.2.0?topic=commands-execio).

Late SMF recording and extraction endpoints can omit records. A wide
date margin does not prove complete input. RC=0 cannot establish that
the largest real-world value was recorded or delivered to SMFIN.

## Remaining boundaries

- No real z/OS/QSAM/TSO execution was available for this review.
- No full RMF reassembly, signature verification or vendor-format support.
- No automatic gap/overlap resolution or elapsed-time weighted aggregation.
- No automatic IPL warm-up removal, UTC timeline or CPC aggregation.
- No guarantee that a valid binary value is physically plausible, or that
  the producer has no release/APAR-specific defects. Check site maintenance
  and compare to an independently trusted formatter on the actual system.
- Source metadata changes intentionally stop a run, including legitimate
  migrations; incomplete identity metadata requires manual verification.

These boundaries are explicit so a successful desktop test is not
mistaken for evidence that every production situation is supported.
Follow [TEST_PLAN.md](TEST_PLAN.md) for the remaining host checks.
