# Agent development contract

Project owner: Yarden Lechner. Runtime: TSO/E REXX on z/OS.

## Current work

Read `docs/SCRT_WORKFLOW.md` and `docs/SCRT_RULES.md` before extending
the CPC calculation. The approved development branch is
`feature/scrt-cpc-aggregation`. Changes, tests and a draft PR on that
branch are authorized for this task. Merge to `main` only when requested
by the owner. Do not submit jobs or operate on a production mainframe.

## Ownership and evidence

- The coordinator assigns one writer to each file. Researchers and
  reviewers send findings; they do not concurrently rewrite owned files.
- Verify domain rules against primary IBM material. Record its version,
  URL and remaining uncertainty in the rules ledger.
- Keep three results distinct: recorded SID peaks, raw hourly CPC LAC,
  and version-specific SCRT report values. Never invent a rule merely
  to reproduce one target value.
- A reviewer must challenge the fixtures and arithmetic independently
  of the developer. Passing tests are evidence for the supported input
  contract, not IBM certification or z/OS acceptance.

## Implementation

- Keep the default SID mode and its CSV/report contracts compatible.
  New CPC behavior is opt-in and must identify unsupported input.
- Production processing remains REXX with no Python runtime dependency.
  Python and Regina are workstation/CI testing tools only.
- REXX and JCL are ASCII text, at most 72 columns before site conversion.
  Preserve the RDW-relative mapping and existing structural guards.
- Do not infer physical identity from SID or sysplex alone. Do not infer
  complete CPC population solely from observed input.
- Keep missing data distinct from measured zero. Do not sum separate
  LPAR peaks or round individual means before CPC aggregation.
- Keep synthetic data and test drivers in `.work/`. Never commit real
  SMF, credentials or sensitive site identifiers to this public repo.

## Publication safeguards

- Public examples must use newly invented measurements, names, times
  and topology, explicitly identified as fictional. Replacing only a
  system name does not make an actual measurement trace fictional.
- Keep real SMF, debug traces, screenshots, dataset/logstream names,
  source inventories and private comparison evidence outside the repo.
  Do not repeat removed private material in commit messages, PR text,
  review findings or a public cleanup log.
- Before publishing, review the final tree, reachable history including
  deleted files, and Git author/committer metadata. Use an owner-approved
  public attribution identity; review metadata for unintended disclosures.
  Owner-approved name and email attribution may remain public.
- Review PR text and CI output/artifacts separately. A file scan does
  not establish that every GitHub surface or external copy is clean.
- Cleaning the latest tree does not erase earlier commits, existing
  clones, forks or cached copies. Any history rewrite needs a separate
  coordinated plan and the owner's authorization.
- After a cleanup, obtain an independent repeat audit and record its
  scope and limits without republishing the removed material. Follow
  `docs/PUBLICATION_REVIEW.md` for a repeatable review.

## Validation and delivery

Run `python tests/run_checks.py regina` and
`python tests/run_cpc_checks.py regina` (an interpreter path may replace
`regina`). Review `git diff --check` and the actual changed source.
Record any remaining host or SCRT parity checks explicitly. Verify the
remote branch commit and CI status before describing delivery as done.
Use a draft PR while SCRT compatibility and site acceptance are pending.
