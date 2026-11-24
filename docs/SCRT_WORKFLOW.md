# SCRT development workflow and agent plan

Owner: Yarden Lechner. Plan established 2026-11-23.
Baseline: `ee6360464babbeaee541fa97a64c867a4f288908` on `main`.
Development branch: `feature/scrt-cpc-aggregation`.

## Outcome and scope

The intended outcome is an explainable reconstruction of the relevant
z/OS SCRT LPAR/CPC figures from SMF, with every contributing interval
traceable. The first development increment is an opt-in **raw hourly CPC
LAC diagnostic**. It is useful for reconciliation, but it is not an N5
or billing reproduction claim.

The existing SID peak tool remains available unchanged by default.
Production execution stays in TSO/E REXX through batch JCL. Multiple
SMF inputs may be concatenated; sysplex boundaries do not determine CPC
membership. No live SMF or site identifiers belong in this public repo.
Tests construct binary records in code. The five-value CPC teaching
sequence is independently invented. Example names and fixture population
counts illustrate test cases and do not establish a verified production
inventory. The input-file count is configurable; the example job does not
describe an installation's topology.

## Agent roles and handoffs

There are four concurrent execution slots. Roles are scheduled in waves;
the table is not a claim that six independent models run at once.

| Role | Responsibility | Deliverable | Must challenge |
|---|---|---|---|
| Coordinator / architect | Scope, file ownership, integration, branch and PR | This plan, interface contract, delivery evidence | Unverified rules entering production logic |
| IBM researcher | Primary sources and version-specific semantics | `SCRT_RULES.md` evidence ledger | Hour assignment, capacity, rounding, reporting clock |
| REXX developer | Shared parser integration and opt-in CPC engine | `src/R4HAMAX.rexx` | Identity, duplicates, incomplete data, legacy behavior |
| Independent test author | Separately built records and exact-value oracle | `tests/run_cpc_checks.py` | A fixture sharing the implementation's mistakes |
| Independent reviewer | Re-read source/diff after implementation | Findings resolved before PR is ready | False coverage, hidden rounding, unsupported claims |
| Site validator (owner) | Actual z/OS and SCRT comparison | Sanitized acceptance evidence | EBCDIC, QSAM, JCL RCs, installed-release behavior |

The researcher takes the reviewer role after research finishes. The test
author calculates expected results independently of REXX stems and its
fixture builder. The coordinator owns docs, JCL and CI; each source/test
file has one writer. Findings flow back to that writer for correction.

### Execution waves

1. **Research and baseline:** coordinator reads the repository and runs
   existing tests; researcher verifies IBM rules; test author challenges
   identity/coverage assumptions; developer designs the interface.
2. **Build and test:** developer edits REXX; test author implements an
   independent suite; coordinator writes runbook/JCL/CI; researcher
   completes the rules ledger.
3. **Review and integrate:** reviewer checks the diff and claims; writer
   fixes concrete findings; both suites run against the final source.
   Coordinator commits to the feature branch and opens a draft PR.
4. **Site comparison:** owner retains field and report evidence in an
   approved private location, or runs the documented checks locally.
   Unresolved SCRT rules are promoted only after this evidence establishes
   their scope. Public fixtures are independently invented afterward.

The GitHub Actions workflow runs deterministic tests. It does **not**
start autonomous LLM agents, schedule research, or need an LLM API key.
The agent workflow above governs development and review sessions.

## Milestones and completion gates

| Stage | Work | Gate / status for this increment |
|---|---|---|
| S0 Baseline | Pin source and preserve legacy behavior | Existing regression suite passes |
| S1 Rule ledger | Record midpoint, average, identity and capacity evidence | Every implemented rule has a source or explicit project-policy label |
| S2 Raw CPC engine | Physical identity, inventory, hour bins, concurrent sums | Complete-hour and adverse-input tests pass |
| S3 Independent review | Review source, exact-value oracle and generated output | Concrete findings fixed; final checks pass |
| S4 Host acceptance | TSO/E, EBCDIC, VBS, dataset concatenation and RCs | Pending site execution; desktop CI cannot close this gate |
| S5 SCRT compatibility | Installed-version report clock, capacity and rounding | Pending real reconciliation evidence; no parity claim yet |

S2 and S3 are the code deliverable in this branch. S4 and S5 are explicit
follow-up gates, not hidden assumptions in the implementation. Product
activity, SMF 89 and final product billing are outside the current z/OS
LPAR/CPC scope.

## First-increment calculation contract

`CPC=Y` selects the new path. Require one `DATE=YYYYDDD`, `SID=*`, and
`HOURLY=Y`. `DAYMODE` continues to control legacy SID mode only.

An explicit `CPCMAP` inventory defines every expected `(CPC,PTN)` for
the selected local day. The CPC key is the hex encoding of the actual
`SMF70POM || SMF70CSC` bytes. PTN is the writing partition number. The
inventory is a required user-supplied population, not a population
inferred from records that happened to arrive.

The initial supported profile is deliberately narrow:

- Exactly 900,000 ms per interval, starting on quarter-hour boundaries.
- One stable, shared raw GMT/local offset within each CPC.
- Zero hypervisor date/time offset and native z/OS LPAR input; known
  simplified VM data is rejected. Site provenance must establish native
  LPAR execution, since absence of a VM flag is not proof by itself.
- LPAR-scoped LAC (`SMF70STF` bit 3 on), usable machine identity and
  stable physical-partition source metadata.
- A fixed declared LPAR population for all 24 hours of the selected day.

These are project support restrictions, **not a statement that IBM SCRT
requires quarter-hour synchronization or rejects every other layout**.
Unaligned or unequal intervals, offset changes and unsupported identity
changes fail explicitly. A gap is reported as incomplete. A permanently
missing expected LPAR therefore cannot disappear from the calculation.

For each physical LPAR and reporting hour, require four distinct slots:

`RAW_LPAR_HOURLY_LAC = (LAC_00 + LAC_15 + LAC_30 + LAC_45) / 4`

An interval is labeled by its midpoint. With this supported profile,
06:45-07:00 is in hour 06, even though its LAC was recorded at the end.
This does not recalculate a second four-hour moving average.

For a complete hour:

`RAW_CPC_HOURLY_LAC = sum(RAW_LPAR_HOURLY_LAC for expected LPARs)`

The report shows the contribution of each LPAR. It selects the CPC peak
by the concurrent sum at full precision. It never adds the maxima of
different LPARs taken from different hours. Equal peaks use the earliest
hour, independent of record arrival order.

Incomplete hours have no numeric CPC total. The peak is labeled
`OBSERVED_COMPLETE_HOUR_PEAK`; if any hour is incomplete it is not a
verified full-day peak. The report enumerates all 24 hours, including
hours where no records arrived. Measured zero is a valid complete value.

Legacy `CSV=Y` remains its existing schema. CPC mode emits a separate,
explicit header including CPC/PTN, timestamps, raw LAC/WLA, offset and
scope information. All values are diagnostic; no capacity correction,
assumed integer billing rounding, or synthetic zero fill is applied.

## Required synthetic evidence

| Scenario | Expected evidence |
|---|---|
| Existing SID behavior | Existing suite unchanged and passing |
| Noncoincident peaks | A/B hours (100,30),(50,90): CPC peak 140, never 190 |
| Separate CPCs and SID collisions | Physical identities stay separate |
| Precision | Two means of 1.5 sum to 3 before display formatting |
| Coverage | Missing slot, whole hour, whole LPAR: INCOMPLETE |
| Zero and upper bound | Zero remains valid; two uint32 maxima sum exactly |
| Duplicate across input files | No change to contribution; counter increments |
| Conflict / unexpected member | RC12; partial output is discarded |
| Unsupported timing | Unequal duration, off-grid start or changed LGO fails |
| Order invariance | Reordering leaves values, completeness and ties unchanged |
| Fictional five-value example | End-label case gives raw 52.5; start-label case 50 |
| Production I/O flow | CPCMAP, batches, EOF, CSV, close failures and RC paths |

The new Python suite constructs binary fixtures independently and uses
exact rational arithmetic for expected means. It exercises the actual
REXX routines and replaces only the TSO I/O layer in desktop simulations.
Python is never required for the production job.

## Reconciliation workflow

The five-value teaching example in [SCRT_RULES.md](SCRT_RULES.md) is
wholly fictional. It demonstrates the following method without disclosing
or claiming to resolve an actual installation's measurements.

1. Record SCRT version, report period, CPC, LPAR and exact report section
   and column. Preserve actual start, duration, LAC, WLA, flags and LGO
   for the relevant records plus adjacent intervals in a private location.
2. Establish whether the labels identify interval starts or ends. In
   the fictional example, end labels give a raw hour-06 mean of 52.5;
   start labels give 50.
3. Trace the exact records contributing to both reports. Compare the
   complete hour and all expected LPARs before comparing maxima.
4. Inspect defined-capacity and WLA-related constraints for the exact
   installed release. In the fictional example, a qualifying cap of 45
   could map raw 52.5 to 45; that hypothetical arithmetic does not
   establish a general rule or a site's actual capacity configuration.
5. Reconcile rounding and peak/tie rules using several boundary cases.
   Do not infer a universal rule from this single output.
6. Only then add an explicitly versioned compatibility mode and a
   frozen, newly invented comparison fixture. Keep raw values alongside
   adjusted values and retain actual supporting evidence privately.

## Git and review workflow

Work on the feature branch; run both suites and `git diff --check` before
committing. The CI workflow checks legacy and CPC modes independently on
push and pull requests. A draft PR links this plan, the evidence ledger,
the runbook and the validation results. No automatic merge is configured.
Review/merge and mainframe execution remain separate owner actions.

Future work should continue from this branch/PR, not create an unrelated
rewrite. Do not add live production samples to make a test pass.
Follow [PUBLICATION_REVIEW.md](PUBLICATION_REVIEW.md), including metadata
and independent repeat review, before publishing changes.
