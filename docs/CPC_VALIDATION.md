# CPC increment validation record

Date: 2026-11-24. Baseline: `ee6360464babbeaee541fa97a64c867a4f288908`.
Branch: `feature/scrt-cpc-aggregation`.

Tests construct binary records in code. The five-value CPC teaching
sequence is independently invented. Example names and fixture population
counts illustrate test cases; they do not establish a verified production
inventory.

## Executed checks

| Check | Observed result |
|---|---|
| Existing `SELFTEST` and `tests/run_checks.py` | PASS on Regina REXX 3.9.5 / Linux |
| New `tests/run_cpc_checks.py` | PASS: 73 scenarios against production REXX |
| Independent reviewer rerun | PASS: the same 73 scenarios |
| Legacy generated example vs `examples/report.txt` | Byte-for-byte equal |
| REXX and JCL transfer constraints | ASCII, all lines at most 72 columns |
| `git diff --check` | PASS before commit |

Commands used locally:

```text
python tests/run_checks.py .tools/regina-run
python tests/run_cpc_checks.py .tools/regina-run
cmp .work/example-report.txt examples/report.txt
git diff --check
```

The ignored wrapper points to a locally extracted Regina package; it is
not a production dependency. CI uses its installed `regina` executable.
The workflow runs legacy and CPC suites as separate jobs. Its live
status is attached to the branch/PR; local results do not imply CI passed.

## Evidence from the new suite

- Independently built binary records use relocated section offsets,
  explicit physical identities and source/time metadata.
- Python `Fraction` supplies expected means, concurrent sums and peak
  comparisons; the REXX fixture builder does not supply the oracle.
- Report values, all 24 hour statuses and omitted numeric totals for
  incomplete hours are checked, in addition to internal aggregates.
- The real entry path runs with only TSO I/O replaced, using fictional
  multi-LPAR and multi-CPC fixtures: 288 records, 256+32 data batches and
  256+1 inventory batches. Fixture sizes exercise batch boundaries and
  do not describe any site's topology.
- Complete input returns RC0; missing/duplicate/warning cases RC4;
  conflicting data, unsupported profiles and I/O failures RC12.
- The 14-column audit CSV, duplicate handling and close operations are
  checked. The generated [CPC example](../examples/cpc-report.txt) comes
  from the production report routine, not a hand-written expected report.

## Review findings resolved

1. A shared LGO alone did not rule out hypervisor clock offsets. The
   restricted profile now rejects nonzero HOF and known simplified VM
   input; native-LPAR provenance remains a documented site requirement.
2. A REXX stem-tail/local-variable name collision in the initial draft
   was corrected. Tests verify the actual emitted CPC identity.
3. Reporting and workflow wording distinguish peak selection from
   Top-N ranking and the observed complete-hour peak from an unverified
   full-day peak.
4. CI checks the delivered commit with `git show --check`, rather than
   treating a clean checkout's empty working diff as whitespace evidence.

No blocking correctness issue was identified in independent source and
oracle review for the declared fixed-grid input profile. This is a
bounded review result, not a guarantee about untested configurations.

## Open acceptance gates

- Actual z/OS TSO/E, EBCDIC transfer, QSAM/VBS and JCL return propagation.
- Site inventory correctness, native-LPAR provenance, actual SMF mapping,
  complete extraction and representative CPU/storage measurements.
- Version-specific SCRT report-time, capacity and rounding reconciliation.
- The fictional five-value example checks the consequences of explicit
  start/end interpretations; its invented target does not establish
  SCRT compatibility or resolve any actual site's measurements.

The code remains a raw diagnostic increment and the PR should stay draft
until the appropriate next-stage evidence is supplied. See
[SCRT_WORKFLOW.md](SCRT_WORKFLOW.md) for the owner and next action at each
gate. The synthetic test suite neither runs SCRT nor submits host jobs.
