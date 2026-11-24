# SCRT evidence ledger and implementation boundaries

Evidence checked: **2026-11-23**. This ledger separates published IBM
behavior from this project's initial supported-input contract. It does
not establish equivalence to an installed SCRT release or certify a
z/OS execution. Record the actual SCRT release when comparing results.

## 1. Evidence and its limits

| Rule | Status | Primary evidence and qualification |
|---|---|---|
| `SMF70LAC` is an existing long-term average; do not apply another four-hour moving average to it. | Verified mapping | IBM's [CPU control section][cpu] defines LAC and the scope controlled by `SMF70STF` bit 3. IBM's [CPU activity conditions][activity] describes it as the value at interval end. |
| Each writing image must supply its own LAC. Other partition information in one image's record is not a collection of every LPAR's LAC. | Verified | IBM's [CP_CPU_LPAR_H][lpar-table] identifies this value as available from the writing partition. |
| For regular intervals, form an hourly average of that LPAR's LAC samples. | Verified for the illustrated regular case | IBM's [2019 white paper][white-paper] gives four 15-minute values, 53, 53, 52 and 50, with hourly result 52. It does not provide a complete irregular-duration or rounding specification. |
| SCRT uses midpoint-based interval-to-hour allocation. | Verified statement, bounded context | [APAR OA64501][midpoint] explicitly describes midpoint allocation while diagnosing H7 completeness accounting. Its example sends 08:59 plus four minutes to hour 09. This establishes the documented mechanism, not tested compatibility for every report section and release. |
| Aggregate concurrent LPAR contributions on the same CPC before finding the CPC peak. | Verified principle | IBM's [software licensing explanation][licensing] demonstrates why peaks from different hours cannot be added. Product calculations additionally depend on where and when each product executes. |
| N5 includes capacity treatment; it is not identical to raw LAC. | Verified, SCRT 30.1 documentation | The [30.1 guide][guide], sections "How SCRT uses SMF and SCRT89 records" and "Detail LPAR Data", describes hourly capacity limits. N5 reflects defined-capacity capping, but excludes product group-cap reductions, mobile-like reductions and TFP adjustments. |
| Local reporting time and internal UTC time are different concerns. | Verified policy, SCRT 30.1 documentation | The [30.1 guide][guide] retains local reporting time for matching zones and describes UTC conversion when differences persist beyond two hours. Hypervisor offsets receive separate treatment. A universal UTC-hour grid is not automatically the same reporting grid. |
| Defined and group capacities need distinct logic. | Verified | IBM's [group-capacity description][group-capacity] applies individual defined-capacity treatment before group treatment for products. It does not prescribe distributing a group reduction back to each N5 LPAR. |
| `STF` bit 3 is a semantic scope flag. | Verified mapping | The [CPU mapping][cpu] describes LAC scope and exclusion of CPU wait. Do not interpret this bit alone as complete input validation. |
| `SMF70LGO` is the GMT-to-local offset in STCK format. | Verified mapping | The [RMF product mapping][product] defines the field. Comparing raw offsets is not the same operation as implementing UTC conversion. |
| Hypervisor clock offsets and simplified guest records need separate handling. | Verified mapping | The [CPU mapping][cpu] places `SMF70HOF` at section offset 40 (eight bytes) and identifies `SMF70INB` bit 5 as simplified z/VM guest data. Bit 5 being OFF alone does not prove a native LPAR. |
| Full product billing has additional inputs and rules. | Verified | IBM's [SCRT overview][overview] identifies SMF70-1 and SMF89 product-use inputs and concurrent product calculations. This project's first increment handles raw z/OS LPAR data only. |

The PDF guide was retrieved through indexed IBM excerpts; direct PDF
retrieval was unavailable during this review. Its version is explicit.
The 2019 white paper is supporting evidence, not a promise that every
current edge case behaves identically.

## 2. Conservative initial project contract

The optional `CPC=Y` calculation is an auditable raw baseline. The
following restrictions are **project choices**, not alleged IBM SCRT
input requirements:

- Select one explicit local date and supply an explicit expected LPAR
  inventory for each CPC. An absent expected LPAR must remain visible.
- Accept fixed 15-minute intervals on quarter-hour boundaries for the
  baseline calculation. The interval's midpoint determines its hour;
  for this restricted input it belongs to the interval-start hour.
- Require the same stable raw LGO within a CPC. Preserve local labels.
  This increment does not implement general UTC, DST or hypervisor
  clock normalization.
- Supply native z/OS LPAR input only. Reject nonzero `SMF70HOF` and
  simplified guest data indicated by `SMF70INB` bit 5 (mask X'04').
  These guards do not replace verifying the input's native-LPAR
  provenance; they are not a general detector of every virtual guest.
- Require LAC scope bit 3 ON for contributions. A structurally valid
  record with different scope must not silently enter a CPC total.
- Keep raw CPC plant/sequence and writer partition identity, rather
  than treating SID or sysplex as a CPC identifier.
- Detect duplicates, conflicts, gaps and overlaps before calling an
  hour complete. Neither sample count alone nor summed duration proves
  complete coverage. Unsupported observations must be reported.
- Require all expected contributions to be complete before accepting
  an hourly CPC total as complete. Missing input is not zero use.
- Keep `RAW_*` result labels and explicit incomplete-hour status.
  A peak among complete observed hours does not establish the peak
  of an incompletely observed day; the report must expose that limit.
- Preserve precision through LPAR means and CPC summation. Display
  formatting is not evidence of SCRT's rounding algorithm.

For eligible hours, the baseline arithmetic is:

\[
R_{l,h}=\frac{1}{4}\sum_{i=1}^{4}LAC_{l,h,i},\qquad
C_{c,h}=\sum_{l\in\operatorname{inventory}(c)}R_{l,h}.
\]

Only concurrent complete `C` values are candidates for a raw CPC peak.
Do not pool all LPAR samples into one average or add independently
selected LPAR peaks. This arithmetic is not a claim of N5 parity.

## 3. Fully fictional five-value teaching example

These measurements, times and the hypothetical target are newly invented
for documentation and tests; they are not derived from production data.
The labels are 06:00=20, 06:15=60, 06:30=40, 06:45=80 and
07:00=30. An invented comparison target of 45 illustrates why a match
to one number cannot establish the calculation rule. Labels alone do
not identify the underlying SMF intervals or report metric.

| Explicit interpretation | Raw result for hour 06 |
|---|---:|
| Labels are ends of contiguous 15-minute intervals; midpoint allocation uses the last four values. | `(60+40+80+30)/4 = 52.5` |
| Labels are starts of contiguous 15-minute intervals; midpoint allocation uses the first four values. | `(20+60+40+80)/4 = 50` |
| All five values averaged together, regardless of interval identity. | `46`; not a justified one-hour calculation |

In the end-label interpretation, a qualifying defined-capacity limit
of 45 could reduce 52.5 to 45. This is an entirely **hypothetical**
capacity example, not evidence about any installation or an implemented
compatibility rule. A separately constructed fixture can test an
established capacity rule. Do not force the invented target by selecting
the middle sample, truncating the five-value mean or applying an
unexplained adjustment.

## 4. Rules not yet established for compatibility

| Open question | Evidence required before a compatibility claim |
|---|---|
| Unequal and partial interval weighting in the target N5 calculation | Version-specific IBM rule or an independent SCRT fixture with unequal durations and known values. Container-specific weighted-average documentation is not sufficient by itself. |
| Integer rounding and its stage | Fixtures around fractional LPAR means, multiple fractional contributions, zero and values below one; establish rounding before/after capping and CPC sum. Do not import another capacity product's rounding policy. |
| Defined-capacity changes within an hour and WLA handling | Actual fields/configuration, documented applicability, changing-capacity fixtures and the target SCRT output. |
| General midpoint allocation and boundary ties | Verify cross-hour, exact midpoint-at-hour, midnight and reporting-period cases against the target release. |
| Time zones, DST and hypervisor offsets | Validate signed offset conversion, fractional-hour offsets, repeated hours, CPC report-time choice and `SMF70HOF`/virtual-clock behavior. |
| Absent, restarted or migrated LPARs | Time-bounded inventory and source records establishing when a contribution is expected. Absence cannot prove inactivity. |
| Difference between a raw result and an SCRT report value | Privately retained interval fields, capacity information and the exact SCRT section/version for the same selected input. |

Keep actual comparison evidence in an approved private location. Retain
CPC/writer identity,
`SMF70DAT`, `SMF70IST`, `SMF70INT`, LAC, WLA, full STF, LGO and relevant
capacity fields. Include adjacent intervals, the exact SCRT version,
input selection and exclusion/control statements. Compare hour-level
contributions before comparing only maxima. Publish only newly invented
fixtures that exercise the established rule, not actual traces with
renamed systems or transformed measurement values.

## 5. Evidence gates for subsequent stages

1. **Raw baseline:** validate the restricted contract above with
   independent synthetic expectations and preserve the existing SID
   behavior. Review code and report labels separately from arithmetic.
2. **N5 compatibility:** resolve capacity, report-time and rounding
   rules against the same SCRT release and input. Keep raw and adjusted
   outputs distinct, including an explanation for every adjustment.
3. **Site acceptance:** verify EBCDIC transfer, actual VBS/EXECIO, source
   identity, interval extraction and representative volume on z/OS.
   Desktop success does not establish these properties.
4. **Broader inputs or billing:** expand duration/time/topology support
   only with evidence and tests. Product billing, mobile/zCAP and TFP
   calculations require their own scope and inputs.

No stage may replace a missing rule with a formula chosen because it
matches one reported number.

[cpu]: https://www.ibm.com/docs/en/zos/3.1.0?topic=s1cpia-cpu-control-section
[activity]: https://www.ibm.com/docs/en/zos/3.2.0?topic=conditions-cpu-activity-smf-record-type-70-1
[lpar-table]: https://www.ibm.com/docs/en/zp-and-ca/3.1.0?topic=tables-cp-cpu-lpar-h
[white-paper]: https://www.ibm.com/support/pages/system/files/inline-files/Are_You_Using_the_Right_4-Hour_Rolling_Average%3F.pdf
[midpoint]: https://www.ibm.com/support/pages/apar/OA64501
[licensing]: https://www.ibm.com/about/software-licensing/assets/zsw_licensing/IBM-Z-Software-Webpages.pdf
[guide]: https://www.ibm.com/docs/en/SSLTBW_3.1.0/pdf/scrt-30-1-0.pdf
[group-capacity]: https://www.ibm.com/docs/en/zos/3.2.0?topic=capacity-how-scrt-uses-group
[product]: https://www.ibm.com/docs/en/zos/3.1.0?topic=mapping-rmf-product-section
[overview]: https://www.ibm.com/docs/en/zos/3.2.0?topic=tool-about-sub-capacity-reporting
